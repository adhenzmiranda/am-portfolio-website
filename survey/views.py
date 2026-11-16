import json
import logging
import uuid

from django.db import transaction
from django.http import Http404, JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404, render
from django.templatetags.static import static
from django.urls import reverse
from django.conf import settings
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit
from markdownify.templatetags.markdownify import markdownify

from projects.views import client_ip

from .logic import SEND_CHOICES, TOKEN_LIFETIME, pick_condition, score
from .models import Participant, Section, Survey
from .validation import SubmissionError, clean_source, clean_submission

logger = logging.getLogger(__name__)

# Generous, because a whole classroom on campus Wi-Fi shares one IP address.
RATE = '300/h'


def review_key(survey):
    """The secret part of the review link (e.g. for a supervisor): try the survey with no
    login, nothing saved. Derived from SECRET_KEY, so it can't be guessed, and it changes
    when the key is rotated or the survey is duplicated as a new version."""
    return salted_hmac('survey-review-link', f'{survey.pk}:{survey.version}').hexdigest()[:24]


def review_url(survey):
    return f'{settings.SITE_URL}/{survey.slug}/?review={review_key(survey)}'


def has_review_key(request, survey):
    given = request.GET.get('review', '')
    return bool(given) and constant_time_compare(given, review_key(survey))


def can_preview(request):
    """Staff who are fully logged in to the admin (password + 2FA)."""
    user = getattr(request, 'user', None)
    if not (user and user.is_authenticated and user.is_staff):
        return False
    is_verified = getattr(user, 'is_verified', None)
    return bool(is_verified and is_verified())


def _md(text):
    """Markdown from the admin as sanitised HTML (django-markdownify runs bleach with the site's allow-list)."""
    return mark_safe(markdownify(text)) if text and text.strip() else ''


def rich_text(survey, sections):
    """The formatted blocks, rendered by the template into <template> tags.

    Kept out of the JSON config on purpose: the page copies these ready-made
    nodes into place, so no HTML is ever built from strings in the browser.
    """
    return {
        'consent': _md(survey.intro_text),
        'thanks': _md(survey.thanks_message),
        'sections': [_md(s.description) for s in sections],
    }


def _url(field):
    return field.url if field else ''


def _download_url(field):
    """Cloudinary URL that downloads instead of opening (for "Save image")."""
    url = _url(field)
    return url.replace('/upload/', '/upload/fl_attachment/', 1) if '/upload/' in url else url


def page_config(request, survey, preview):
    sections = list(survey.sections.prefetch_related('questions'))
    share_url = request.build_absolute_uri(survey.get_absolute_url())
    return {
        'mode': 'preview' if preview else 'live',
        'slug': survey.slug,
        'title': survey.title,
        'version': survey.version,
        'storageKey': f'survey:{survey.slug}:v{survey.version}',
        'csrfToken': get_token(request),
        'startUrl': reverse('survey:start', args=[survey.slug]),
        'submitUrl': reverse('survey:submit', args=[survey.slug]),
        'logo': static('assets/images/navbar/PortfolioLogo.svg'),
        'handle': survey.post_handle,
        'consent': {
            'heading': survey.intro_heading,
            'statements': survey.consent_list(),
            'startLabel': survey.start_label,
            'researcherEmail': survey.researcher_email,
            'ethicsContact': survey.ethics_contact,
        },
        'sections': [{
            'kind': s.kind,
            'title': s.title,
            'button': s.button_label,
            'questions': [{
                'code': q.code,
                'text': q.text,
                'help': q.help_text,
                'kind': q.kind,
                'required': q.required,
                'options': q.option_list(),
                'min': q.min_value,
                'max': q.max_value,
                'rangeMessage': q.range_message,
                'low': q.scale_low_label,
                'high': q.scale_high_label,
                # Researcher view only (preview): group labels and attention answers stay off live pages.
                **({'construct': q.construct, 'attention': q.attention_answer} if preview else {}),
            } for q in s.questions.all()] if s.kind == Section.QUESTIONS else [],
        } for s in sections],
        'prompts': [{
            'n': p.number,
            'text': p.text,
            'screenshot': _url(p.screenshot),
            'mock': p.builtin_mock,
            'contextImage': _url(p.context_image),
            'contextMock': p.context_mock,
            'contextLabel': p.context_label,
            'pair': p.pair_group.strip().upper(),
            **({'risky': p.risky} if preview else {}),   # the answer key only goes to your preview
        } for p in survey.prompts.all()],
        'sendChoices': SEND_CHOICES,
        'conditions': [{
            'key': c.key,
            'name': c.name,
            'kind': c.kind,
            'video': _url(c.video),
            'image': _url(c.image),
            'text': c.text_body,
            'caption': c.caption,
            'alt': c.alt_text,
        } for c in survey.conditions.filter(active=True)],
        'thanks': {
            'heading': survey.thanks_heading,
            'shareImage': _url(survey.share_image),
            'shareImageDownload': _download_url(survey.share_image),
            'shareText': survey.share_text,
            'shareUrl': share_url,
            'alreadyDone': survey.already_done_message,
        },
    }


def _no_index(response):
    response['X-Robots-Tag'] = 'noindex, nofollow'
    response['Cache-Control'] = 'no-store'
    return response


def survey_page(request, slug):
    survey = get_object_or_404(Survey, slug=slug)
    # Preview: you (logged in) with ?preview=1, or anyone holding the review link.
    preview = ('preview' in request.GET and can_preview(request)) or has_review_key(request, survey)
    if not preview:
        if survey.status == Survey.DRAFT:
            raise Http404
        if survey.status == Survey.CLOSED:
            return _no_index(render(request, 'survey/closed.html', {'survey': survey}))
    return _no_index(render(request, 'survey/survey.html', {
        'survey': survey,
        'preview': preview,
        'config': page_config(request, survey, preview),
        'rich': rich_text(survey, survey.sections.all()),
    }))


def _json_error(code, status):
    return JsonResponse({'error': code}, status=status)


def _parse_json(request):
    try:
        return json.loads(request.body or b'{}')
    except (ValueError, UnicodeDecodeError):
        return None


@require_POST
@ratelimit(key=client_ip, rate=RATE, method='POST', block=False)
def start(request, slug):
    survey = get_object_or_404(Survey, slug=slug)
    if survey.status != Survey.OPEN:
        return _json_error('closed', 410)
    if getattr(request, 'limited', False):
        return _json_error('rate_limited', 429)
    data = _parse_json(request)
    if not isinstance(data, dict):
        return _json_error('bad_request', 400)
    condition = pick_condition(survey, survey.batch)
    if condition is None:
        logger.error('Survey %s is open but has no active media groups.', survey.slug)
        return _json_error('not_ready', 503)
    participant = Participant.objects.create(
        survey=survey, survey_version=survey.version, batch=survey.batch,
        condition=condition, source=clean_source(data.get('source')),
    )
    return JsonResponse({'token': str(participant.token), 'condition': condition.key})


@require_POST
@ratelimit(key=client_ip, rate=RATE, method='POST', block=False)
def submit(request, slug):
    survey = get_object_or_404(Survey, slug=slug)
    if survey.status != Survey.OPEN:
        return _json_error('closed', 410)
    if getattr(request, 'limited', False):
        return _json_error('rate_limited', 429)
    data = _parse_json(request)
    if not isinstance(data, dict):
        return _json_error('bad_request', 400)
    try:
        token = uuid.UUID(str(data.get('token')))
    except ValueError:
        return _json_error('bad_token', 400)

    with transaction.atomic():
        # Lock the row so a double tap can't submit twice.
        participant = (Participant.objects.select_for_update()
                       .select_related('condition').filter(survey=survey, token=token).first())
        if (participant is None or participant.completed
                or participant.started_at < timezone.now() - TOKEN_LIFETIME):
            return _json_error('expired', 410)
        try:
            cleaned = clean_submission(survey, participant.condition, data)
        except SubmissionError as exc:
            logger.warning('Survey %s: rejected submission (%s)', survey.slug, exc)
            return _json_error('invalid', 400)
        for field, value in cleaned.items():
            setattr(participant, field, value)
        prompts = list(survey.prompts.all())
        participant.before_score = score(prompts, participant.before_answers)
        participant.after_score = score(prompts, participant.after_answers)
        participant.score_change = participant.after_score - participant.before_score
        participant.completed_at = timezone.now()
        participant.save()
    return JsonResponse({'ok': True})
