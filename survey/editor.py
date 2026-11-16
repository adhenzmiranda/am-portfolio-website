"""
The Google Forms-style editor at /<address>/edit/ (staff with 2FA only).

The page (templates/survey/editor.html + static/survey/editor.js) autosaves
through the small JSON API below. Every change goes through a ModelForm, so
the same validation as the admin applies, and the content lock is enforced
here too: once a survey has responses, only settings that don't change what
participants answer can be edited.
"""
import json
import logging
from functools import wraps

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max
from django.forms.models import model_to_dict, modelform_factory
from django.http import Http404, JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.conf import settings
from django.views.decorators.http import require_GET, require_POST

from projects.direct_upload import DirectUploadField, signed_upload_params

from .admin import LOCKED_SURVEY_FIELDS, duplicate_survey
from .logic import progress
from .models import BUILTIN_MOCKS, Condition, Prompt, Question, Section, Survey
from .views import can_preview, review_url

logger = logging.getLogger(__name__)

SURVEY_FIELDS = (
    'title', 'slug', 'status', 'batch', 'target_responses', 'ethics_reference',
    'intro_heading', 'intro_text', 'consent_statements', 'start_label', 'researcher_email', 'ethics_contact',
    'closed_heading', 'closed_message', 'thanks_heading', 'thanks_message', 'share_text', 'already_done_message',
    'post_handle',
)
MODELS = {
    'survey': (Survey, SURVEY_FIELDS),
    'section': (Section, ('kind', 'title', 'description', 'button_label')),
    'question': (Question, ('code', 'text', 'help_text', 'kind', 'required', 'options', 'min_value', 'max_value',
                            'range_message', 'scale_low_label', 'scale_high_label', 'construct', 'attention_answer')),
    'prompt': (Prompt, ('number', 'text', 'builtin_mock', 'context_label', 'context_mock', 'risky', 'pair_group')),
    'condition': (Condition, ('key', 'name', 'kind', 'text_body', 'caption', 'alt_text', 'active')),
}
IMAGE_FIELDS = {'survey': {'share_image'}, 'prompt': {'screenshot', 'context_image'}, 'condition': {'image'}}
MAX_IMAGE_MB = 10
NEW_SECTION_TITLES = {
    Section.QUESTIONS: 'Untitled page',
    Section.INFO: 'Untitled page',
    Section.TASK_BEFORE: 'Would you send this?',
    Section.MEDIA: 'Take a look at this',
    Section.TASK_AFTER: 'Would you send this?',
}


# ---------------------------------------------------------------- access

def editor_required(api=True):
    """Staff with 2FA only. Pages redirect to the admin login; API calls get a 403."""
    def decorator(view):
        @wraps(view)
        def wrapped(request, slug, *args, **kwargs):
            if not can_preview(request):
                if api:
                    return JsonResponse({'error': 'Your admin login has expired. Log in again in another tab, then retry.'}, status=403)
                return redirect(f"{reverse('admin:login')}?next={request.get_full_path()}")
            survey = get_object_or_404(Survey, slug=slug)
            response = view(request, survey, *args, **kwargs)
            response['X-Robots-Tag'] = 'noindex, nofollow'
            response['Cache-Control'] = 'no-store'
            return response
        return wrapped
    return decorator


def _body(request):
    try:
        data = json.loads(request.body or b'{}')
    except (ValueError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _error(message, status=400, **extra):
    return JsonResponse({'error': message, **extra}, status=status)


LOCKED_MESSAGE = ('This survey has responses, so what participants see is locked. '
                  'Use "Duplicate as a new version" in Settings to make changes.')


def _get_item(survey, model, pk):
    if model == 'survey':
        return survey
    if model == 'section':
        return get_object_or_404(Section, pk=pk, survey=survey)
    if model == 'question':
        return get_object_or_404(Question, pk=pk, section__survey=survey)
    if model == 'prompt':
        return get_object_or_404(Prompt, pk=pk, survey=survey)
    if model == 'condition':
        return get_object_or_404(Condition, pk=pk, survey=survey)
    raise Http404


# ---------------------------------------------------------------- JSON shapes

def _url(field):
    return field.url if field else ''


def ser_question(q):
    data = model_to_dict(q, fields=MODELS['question'][1])
    data.update(id=q.pk, order=q.order, section=q.section_id)
    return data


def ser_section(s):
    data = model_to_dict(s, fields=MODELS['section'][1])
    data.update(id=s.pk, order=s.order, questions=[ser_question(q) for q in s.questions.all()])
    return data


def ser_prompt(p):
    data = model_to_dict(p, fields=MODELS['prompt'][1])
    data.update(id=p.pk, screenshot=_url(p.screenshot), context_image=_url(p.context_image))
    return data


def ser_condition(c):
    data = model_to_dict(c, fields=MODELS['condition'][1])
    data.update(id=c.pk, video=_url(c.video), image=_url(c.image), responses=c.participants.count())
    return data


def ser_survey(s):
    data = model_to_dict(s, fields=SURVEY_FIELDS)
    data.update(id=s.pk, version=s.version, share_image=_url(s.share_image))
    return data


SERIALIZERS = {'survey': ser_survey, 'section': ser_section, 'question': ser_question,
               'prompt': ser_prompt, 'condition': ser_condition}


def state(survey):
    return {
        'survey': ser_survey(survey),
        'locked': survey.is_locked,
        'sections': [ser_section(s) for s in survey.sections.prefetch_related('questions')],
        'prompts': [ser_prompt(p) for p in survey.prompts.all()],
        'conditions': [ser_condition(c) for c in survey.conditions.all()],
        'problems': survey.open_problems(),
        'progress': progress(survey),
        'links': {
            'public': f'{settings.SITE_URL}/{survey.slug}/',
            'review': review_url(survey),
            'preview': f'/{survey.slug}/?preview=1',
            'editor': f'/{survey.slug}/edit/',
            'api': f'/{survey.slug}/edit/api/',
            'admin': reverse('admin:survey_survey_change', args=[survey.pk]),
            'qr': reverse('admin:survey_survey_qr', args=[survey.pk]),
            'export': reverse('admin:survey_survey_export', args=[survey.pk]),
        },
    }


def _saved(survey, item=None, model=None):
    survey.refresh_from_db()
    data = {'ok': True, 'problems': survey.open_problems(), 'locked': survey.is_locked,
            'status': survey.status}
    if item is not None:
        data['item'] = SERIALIZERS[model](item)
    return JsonResponse(data)


# ---------------------------------------------------------------- uniqueness within one survey

def _taken(survey, model, field, value, exclude_pk=None):
    if model == 'question':
        qs = Question.objects.filter(section__survey=survey, code=value)
    elif model == 'prompt':
        qs = survey.prompts.filter(number=value)
    else:
        qs = survey.conditions.filter(key=value)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    return qs.exists()


UNIQUE_FIELDS = {'question': ('code', 'This code is already used by another question.'),
                 'prompt': ('number', 'Another prompt already has this number.'),
                 'condition': ('key', 'Another media group already uses this id.')}


def _free(survey, model, base):
    """base, base_2, base_3... whichever is free in this survey."""
    value, n = base, 2
    while _taken(survey, model, None, value):
        value, n = f'{base}_{n}', n + 1
    return value


# ---------------------------------------------------------------- views

CHOICES = {
    'status': Survey.STATUS_CHOICES,
    'sectionKinds': Section.KIND_CHOICES,
    'questionKinds': Question.KIND_CHOICES,
    'optionKinds': sorted(Question.OPTION_KINDS),
    'conditionKinds': Condition.KIND_CHOICES,
    'mocks': BUILTIN_MOCKS,
    'lockedFields': list(LOCKED_SURVEY_FIELDS),
    'maxImageMb': MAX_IMAGE_MB,
}


@editor_required(api=False)
@require_GET
def editor_page(request, survey):
    # The page is only a shell: editor.js loads everything from api_state, so no
    # data is read back out of the page. get_token() sets the CSRF cookie the API calls use.
    get_token(request)
    return render(request, 'survey/editor.html', {'survey': survey})


@editor_required()
@require_GET
def api_state(request, survey):
    return JsonResponse({**state(survey), 'choices': CHOICES})


@editor_required()
@require_POST
def api_update(request, survey, model, pk):
    if model not in MODELS:
        raise Http404
    patch = _body(request)
    if patch is None:
        return _error('Bad request.')
    item = _get_item(survey, model, pk)
    Model, fields = MODELS[model]
    video = patch.pop('video', None) if model == 'condition' else None
    unknown = set(patch) - set(fields)
    if unknown:
        return _error(f'Unknown field: {sorted(unknown)[0]}')
    if survey.is_locked and (model != 'survey' or set(patch) & set(LOCKED_SURVEY_FIELDS) or video is not None):
        return _error(LOCKED_MESSAGE, status=403)

    old_slug = survey.slug   # before validation copies the new values onto the object
    data = model_to_dict(item, fields=fields)
    data.update(patch)
    form = modelform_factory(Model, fields=fields)(data, instance=item)
    if not form.is_valid():
        return JsonResponse({'errors': {f: [str(m) for m in msgs] for f, msgs in form.errors.items()}}, status=400)
    if model in UNIQUE_FIELDS:
        field, message = UNIQUE_FIELDS[model]
        if field in patch and _taken(survey, model, field, form.cleaned_data[field], exclude_pk=item.pk):
            return JsonResponse({'errors': {field: [message]}}, status=400)
    if video:
        try:
            form.instance.video = DirectUploadField('survey_video').clean(video)
        except ValidationError:
            return _error('The video upload could not be verified. Please upload it again.')
    form.save()
    response = _saved(survey, item, model)
    if model == 'survey' and item.slug != old_slug:
        payload = json.loads(response.content)
        payload['redirect'] = f'/{item.slug}/edit/'
        return JsonResponse(payload)
    return response


@editor_required()
@require_POST
def api_create(request, survey, model):
    if survey.is_locked:
        return _error(LOCKED_MESSAGE, status=403)
    body = _body(request)
    if body is None:
        return _error('Bad request.')
    if model == 'section':
        kind = body.get('kind')
        if kind not in dict(Section.KIND_CHOICES):
            return _error('Unknown page type.')
        order = (survey.sections.aggregate(m=Max('order'))['m'] or 0) + 1
        item = Section.objects.create(survey=survey, kind=kind, title=NEW_SECTION_TITLES[kind], order=order)
    elif model == 'question':
        try:
            section = Section.objects.get(pk=int(body.get('section')), survey=survey, kind=Section.QUESTIONS)
        except (TypeError, ValueError, Section.DoesNotExist):
            return _error('Pick a questions page.')
        kind = body.get('kind') or Question.CHOICE
        if kind not in dict(Question.KIND_CHOICES):
            return _error('Unknown question type.')
        order = (section.questions.aggregate(m=Max('order'))['m'] or 0) + 1
        item = Question.objects.create(
            section=section, order=order, kind=kind, code=_free(survey, 'question', 'question'),
            text='Untitled question', options='Option 1' if kind in Question.OPTION_KINDS else '')
    elif model == 'prompt':
        number = (survey.prompts.aggregate(m=Max('number'))['m'] or 0) + 1
        item = Prompt.objects.create(survey=survey, number=number, text='New message')
    elif model == 'condition':
        kind = body.get('kind') or Condition.IMAGE
        if kind not in dict(Condition.KIND_CHOICES):
            return _error('Unknown media type.')
        order = (survey.conditions.aggregate(m=Max('order'))['m'] or 0) + 1
        item = Condition.objects.create(survey=survey, kind=kind, order=order, name='New media group',
                                        key=_free(survey, 'condition', 'group'))
    else:
        raise Http404
    return _saved(survey, item, model)


@editor_required()
@require_POST
def api_delete(request, survey, model, pk):
    if model == 'survey' or model not in MODELS:
        raise Http404
    if survey.is_locked:
        return _error(LOCKED_MESSAGE, status=403)
    _get_item(survey, model, pk).delete()
    return _saved(survey)


@editor_required()
@require_POST
def api_duplicate_question(request, survey, pk):
    if survey.is_locked:
        return _error(LOCKED_MESSAGE, status=403)
    original = _get_item(survey, 'question', pk)
    with transaction.atomic():
        siblings = list(original.section.questions.all())
        copy = Question.objects.get(pk=original.pk)
        copy.pk = None
        copy.code = _free(survey, 'question', f'{original.code}_copy')
        copy.save()
        ordered = []
        for q in siblings:
            ordered.append(q)
            if q.pk == original.pk:
                ordered.append(copy)
        for i, q in enumerate(ordered, 1):
            if q.order != i:
                q.order = i
                q.save(update_fields=['order'])
    return _saved(survey, copy, 'question')


@editor_required()
@require_POST
def api_reorder(request, survey):
    """{"kind": "section", "ids": [...]} or {"kind": "question", "section": id, "ids": [...]}.
    Questions may come from another page (dragged across); they move to `section`."""
    if survey.is_locked:
        return _error(LOCKED_MESSAGE, status=403)
    body = _body(request) or {}
    ids = body.get('ids')
    if not isinstance(ids, list) or not all(isinstance(i, int) and not isinstance(i, bool) for i in ids) \
            or len(set(ids)) != len(ids):
        return _error('Bad order.')
    with transaction.atomic():
        if body.get('kind') == 'section':
            sections = {s.pk: s for s in survey.sections.all()}
            if set(ids) != set(sections):
                return _error('Bad order.')
            for i, pk in enumerate(ids, 1):
                Section.objects.filter(pk=pk).update(order=i)
        elif body.get('kind') == 'question':
            try:
                target = Section.objects.get(pk=int(body.get('section')), survey=survey, kind=Section.QUESTIONS)
            except (TypeError, ValueError, Section.DoesNotExist):
                return _error('Questions can only go on a questions page.')
            if Question.objects.filter(pk__in=ids, section__survey=survey).count() != len(ids):
                return _error('Bad order.')
            for i, pk in enumerate(ids, 1):
                Question.objects.filter(pk=pk).update(order=i, section=target)
        else:
            return _error('Bad order.')
    return _saved(survey)


@editor_required()
@require_POST
def api_upload(request, survey, model, pk, field):
    if field not in IMAGE_FIELDS.get(model, ()):
        raise Http404
    if survey.is_locked and model != 'survey':
        return _error(LOCKED_MESSAGE, status=403)
    item = _get_item(survey, model, pk)
    if request.POST.get('clear'):
        setattr(item, field, None)
        item.save(update_fields=[field])
        return _saved(survey, item, model)
    upload = request.FILES.get('file')
    if not upload:
        return _error('Choose an image.')
    if not (upload.content_type or '').startswith('image/'):
        return _error('That file is not an image.')
    if upload.size > MAX_IMAGE_MB * 1024 * 1024:
        return _error(f'Images can be up to {MAX_IMAGE_MB} MB (Cloudinary free plan). Export it smaller and try again.')
    setattr(item, field, upload)
    try:
        item.save(update_fields=[field])   # CloudinaryField uploads it here
    except Exception:  # noqa: BLE001 - report any upload failure to the editor
        logger.exception('Survey editor: image upload failed')
        return _error('The upload to Cloudinary failed. Please try again.', status=502)
    return _saved(survey, item, model)


@editor_required()
@require_POST
def api_sign_video(request, survey):
    if survey.is_locked:
        return _error(LOCKED_MESSAGE, status=403)
    return JsonResponse(signed_upload_params('survey_video'))


@editor_required()
@require_POST
def api_duplicate_survey(request, survey):
    copy = duplicate_survey(survey)
    return JsonResponse({'ok': True, 'redirect': f'/{copy.slug}/edit/'})
