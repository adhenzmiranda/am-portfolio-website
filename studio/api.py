"""
Studio's JSON API. The pages autosave through it, a field at a time.

Every write goes through a ModelForm with an explicit field list, so the same
validation as the Django admin applies (including the models' own clean()).
Child items (cards, photos...) are always looked up through their project, so an
id from another project is a 404.
"""
import json
import logging

from django.db import transaction
from django.db.models import Count, Max, Q
from django.forms.models import model_to_dict, modelform_factory
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.text import slugify
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from django.core.exceptions import ValidationError
from markdownify.templatetags.markdownify import markdownify

from projects.direct_upload import UPLOAD_KINDS, DirectUploadField, signed_upload_params
from projects.markdown_import import parse_markdown_cards, serialize_cards_to_markdown
from projects.models import (ALLOWED_EMBED_DOMAINS, TECH_STACK_CHOICES, Category, ProjectCard, ProjectEmbed,
                             ProjectPhoto, Projects, ProjectVideo)

from .access import studio_api

logger = logging.getLogger(__name__)

PROJECT_FIELDS = ('name', 'description', 'year', 'featured', 'category', 'technologies', 'display_mode')
CARD_FIELDS = ('title', 'teaser', 'body', 'takeaways_raw', 'visual_placeholder')
IMAGE_FIELDS = {'project': {'thumbnail_image'}, 'card': {'image'}}
MAX_IMAGE_MB = 10
MAX_IMPORT_CHARS = 300_000   # a long article is ~60k; this leaves plenty of room
YEAR_RANGE = (1990, 2100)
MODES = [('portfolio', 'Portfolio'), ('blogpost', 'Blog Post')]

# Photos, videos and embeds share one set of endpoints: /media/<kind>/...
# Photos and videos are uploaded by the browser straight to Cloudinary ("upload" names the
# signed-upload kind in projects/direct_upload.py); the server only verifies and saves the reference.
MEDIA = {
    'photos': {'model': ProjectPhoto, 'fields': ('caption',), 'upload': 'photo', 'file': 'image'},
    'videos': {'model': ProjectVideo, 'fields': ('caption',), 'upload': 'video', 'file': 'video'},
    'embeds': {'model': ProjectEmbed, 'fields': ('embed_code', 'caption'), 'upload': None, 'file': None},
}


# ---------------------------------------------------------------- helpers

def _body(request):
    try:
        data = json.loads(request.body or b'{}')
    except (ValueError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _error(message, status=400):
    return JsonResponse({'error': message}, status=status)


def _form_errors(form, non_field_to=None):
    """Field errors as JSON. A model's clean() error (e.g. the embed check) has no field, so it can be
    shown under `non_field_to` instead."""
    errors = {f: [str(m) for m in msgs] for f, msgs in form.errors.items()}
    if non_field_to and '__all__' in errors:
        errors.setdefault(non_field_to, []).extend(errors.pop('__all__'))
    return JsonResponse({'errors': errors}, status=400)


def _url(field):
    return field.url if field else ''


def _save_patch(item, fields, patch, extra_check=None):
    """Validate a partial update with a ModelForm built for these fields; returns (ok, response_or_None)."""
    unknown = set(patch) - set(fields)
    if unknown:
        return False, _error(f'Unknown field: {sorted(unknown)[0]}')
    data = model_to_dict(item, fields=fields)
    data.update(patch)
    form = modelform_factory(type(item), fields=fields)(data, instance=item)
    if not form.is_valid():
        return False, _form_errors(form, non_field_to=fields[0])
    if extra_check:
        problem = extra_check(form.cleaned_data)
        if problem:
            return False, JsonResponse({'errors': problem}, status=400)
    form.save()
    return True, None


def _upload_image(item, field, request):
    """Thumbnails and card images go through the server (10 MB or less, well within Heroku's limit)."""
    if request.POST.get('clear'):
        setattr(item, field, None)
        item.save(update_fields=[field])
        return None
    upload = request.FILES.get('file')
    if not upload:
        return _error('Choose an image.')
    if not (upload.content_type or '').startswith('image/'):
        return _error('That file is not an image.')
    if upload.size > MAX_IMAGE_MB * 1024 * 1024:
        return _error(f'Images can be up to {MAX_IMAGE_MB} MB (Cloudinary free plan). Export it smaller and try again.')
    setattr(item, field, upload)
    try:
        with transaction.atomic():   # a savepoint, so a failed upload can't poison an outer transaction
            item.save(update_fields=[field])   # CloudinaryField uploads it here
    except Exception:  # noqa: BLE001 - report any upload failure to the editor
        logger.exception('Studio: image upload failed')
        item.refresh_from_db(fields=[field])
        return _error('The upload to Cloudinary failed. Please try again.', status=502)
    return None


# ---------------------------------------------------------------- shapes

def ser_card(card):
    data = model_to_dict(card, fields=CARD_FIELDS)
    data.update(id=card.pk, order=card.order, image=_url(card.image))
    return data


def ser_media(kind, item):
    data = {'id': item.pk, 'order': item.order, 'caption': item.caption}
    if kind == 'photos':
        data['url'] = _url(item.image)
    elif kind == 'videos':
        data['url'] = _url(item.video)
    else:
        data.update(embed_code=item.embed_code, src=item.safe_src if item.is_safe else '')
    return data


def ser_project_summary(p):
    return {
        'id': p.pk, 'name': p.name, 'year': p.year, 'featured': p.featured, 'mode': p.display_mode,
        'category': p.category.name if p.category else '', 'category_id': p.category_id,
        'thumbnail': _url(p.thumbnail_image), 'updated': p.updated_at.isoformat(),
        'editor': reverse('studio:project', args=[p.pk]), 'public': p.get_absolute_url(),
    }


def ser_project(p):
    data = model_to_dict(p, fields=PROJECT_FIELDS)
    data['technologies'] = list(p.technologies or [])
    data.update(id=p.pk, thumbnail_image=_url(p.thumbnail_image), updated=p.updated_at.isoformat())
    return data


def choices():
    return {
        'categories': [[c.pk, c.name] for c in Category.objects.all()],
        'technologies': [[group, [[k, v] for k, v in items]] for group, items in TECH_STACK_CHOICES],
        'modes': MODES,
        'yearRange': YEAR_RANGE,
        'maxImageMb': MAX_IMAGE_MB,
        'maxUploadMb': {kind: UPLOAD_KINDS[spec['upload']]['max_mb'] for kind, spec in MEDIA.items() if spec['upload']},
        'embedDomains': ALLOWED_EMBED_DOMAINS,
    }


def project_state(p):
    media = {kind: [ser_media(kind, m) for m in getattr(p, kind).all()] for kind in MEDIA}
    return {
        'project': ser_project(p),
        'cards': [ser_card(c) for c in p.cards.all()],
        **media,   # photos, videos, embeds
        'counts': {kind: len(items) for kind, items in media.items()},
        'choices': choices(),
        'links': {
            'public': p.get_absolute_url(),
            'admin': reverse('admin:projects_projects_change', args=[p.pk]),
            'projects': reverse('studio:projects'),
            'export': reverse('studio:api_cards_export', args=[p.pk]),
        },
    }


def _year_check(cleaned):
    year = cleaned.get('year')
    if year is not None and not YEAR_RANGE[0] <= year <= YEAR_RANGE[1]:
        return {'year': [f'Use a year between {YEAR_RANGE[0]} and {YEAR_RANGE[1]}.']}
    return None


# ---------------------------------------------------------------- dashboard and lists

@studio_api
@require_GET
def dashboard(request):
    totals = Projects.objects.aggregate(
        total=Count('id'), featured=Count('id', filter=Q(featured=True)),
        blog=Count('id', filter=Q(display_mode='blogpost')))
    recent = Projects.objects.select_related('category').order_by('-updated_at')[:6]
    return JsonResponse({
        'counts': {**totals, 'portfolio': totals['total'] - totals['blog']},
        'recent': [ser_project_summary(p) for p in recent],
        'links': {
            'projects': reverse('studio:projects'),
            'survey': '/msc-survey/edit/',
            'admin': reverse('admin:index'),
            'site': '/',
        },
    })


@studio_api
@require_GET
def projects(request):
    items = Projects.objects.select_related('category').order_by('-year', '-created_at')
    return JsonResponse({
        'projects': [ser_project_summary(p) for p in items],
        'categories': choices()['categories'],
        'modes': MODES,
    })


@studio_api
@require_POST
def project_create(request):
    body = _body(request) or {}
    name = str(body.get('name', '')).strip()
    if not name:
        return _error('Give the project a name.')
    if Projects.objects.filter(name__iexact=name).exists():
        return JsonResponse({'errors': {'name': ['A project with this name already exists.']}}, status=400)
    form = modelform_factory(Projects, fields=PROJECT_FIELDS)({
        'name': name, 'description': 'Write about this project here.', 'year': _this_year(),
        'featured': False, 'category': None, 'technologies': [], 'display_mode': body.get('mode') or 'portfolio'})
    if not form.is_valid():
        return _form_errors(form)
    project = form.save()
    return JsonResponse({'ok': True, 'project': ser_project_summary(project)})


def _this_year():
    return timezone.now().year


@studio_api
@require_POST
def category_create(request):
    name = str((_body(request) or {}).get('name', '')).strip()
    if not name:
        return _error('Type a category name.')
    existing = Category.objects.filter(name__iexact=name).first()
    category = existing or Category.objects.create(name=name[:50])
    return JsonResponse({'ok': True, 'category': [category.pk, category.name], 'categories': choices()['categories']})


@studio_api
@require_POST
def preview(request):
    """Markdown rendered exactly as the live project page renders it (django-markdownify + bleach)."""
    text = str((_body(request) or {}).get('markdown', ''))[:200000]
    return JsonResponse({'html': str(markdownify(text)) if text.strip() else ''})


# ---------------------------------------------------------------- one project

@studio_api
@require_http_methods(['GET', 'POST'])
def project(request, pk):
    item = get_object_or_404(Projects, pk=pk)
    if request.method == 'GET':
        return JsonResponse(project_state(item))
    patch = _body(request)
    if patch is None:
        return _error('Bad request.')
    ok, response = _save_patch(item, PROJECT_FIELDS, patch, extra_check=_year_check)
    if not ok:
        return response
    item.refresh_from_db()
    return JsonResponse({'ok': True, 'item': ser_project(item)})


@studio_api
@require_POST
def project_delete(request, pk):
    item = get_object_or_404(Projects, pk=pk)
    item.delete()
    return JsonResponse({'ok': True, 'redirect': reverse('studio:projects')})


@studio_api
@require_POST
def project_upload(request, pk, field):
    if field not in IMAGE_FIELDS['project']:
        raise Http404
    item = get_object_or_404(Projects, pk=pk)
    problem = _upload_image(item, field, request)
    if problem:
        return problem
    return JsonResponse({'ok': True, 'item': ser_project(item)})


# ---------------------------------------------------------------- cards (Portfolio sections)

def _card(pk, cid):
    return get_object_or_404(ProjectCard, pk=cid, project_id=pk)


@studio_api
@require_POST
def card_create(request, pk):
    project_obj = get_object_or_404(Projects, pk=pk)
    order = (project_obj.cards.aggregate(m=Max('order'))['m'] or 0) + 1
    card = ProjectCard.objects.create(project=project_obj, order=order, title='New section',
                                      teaser='A one-line summary of this section.', body='Write this section here.')
    return JsonResponse({'ok': True, 'item': ser_card(card)})


@studio_api
@require_POST
def card_update(request, pk, cid):
    card = _card(pk, cid)
    patch = _body(request)
    if patch is None:
        return _error('Bad request.')
    ok, response = _save_patch(card, CARD_FIELDS, patch)
    if not ok:
        return response
    return JsonResponse({'ok': True, 'item': ser_card(card)})


@studio_api
@require_POST
def card_delete(request, pk, cid):
    _card(pk, cid).delete()
    return JsonResponse({'ok': True})


@studio_api
@require_POST
def card_upload(request, pk, cid, field):
    if field not in IMAGE_FIELDS['card']:
        raise Http404
    card = _card(pk, cid)
    problem = _upload_image(card, field, request)
    if problem:
        return problem
    return JsonResponse({'ok': True, 'item': ser_card(card)})


@studio_api
@require_POST
def cards_reorder(request, pk):
    project_obj = get_object_or_404(Projects, pk=pk)
    ids = (_body(request) or {}).get('ids')
    own = set(project_obj.cards.values_list('pk', flat=True))
    if not isinstance(ids, list) or set(ids) != own or len(ids) != len(own):
        return _error('Bad order.')
    with transaction.atomic():
        for i, cid in enumerate(ids, 1):
            ProjectCard.objects.filter(pk=cid).update(order=i)
    return JsonResponse({'ok': True})


@studio_api
@require_POST
def cards_import(request, pk):
    """{"markdown": "...", "commit": false} previews; "commit": true creates (append, or "replace": true)."""
    project_obj = get_object_or_404(Projects, pk=pk)
    body = _body(request) or {}
    text = str(body.get('markdown', ''))
    if len(text) > MAX_IMPORT_CHARS:
        return _error(f'That is too long to import at once (over {MAX_IMPORT_CHARS // 1000}k characters). Split it into parts.')
    cards, errors = parse_markdown_cards(text)
    preview_data = {
        'cards': [{'title': c.title, 'teaser': c.teaser, 'words': c.word_count, 'takeaways': c.takeaway_count} for c in cards],
        'errors': [{'index': e.index, 'title': e.title, 'message': e.message} for e in errors],
        'existing': project_obj.cards.count(),
    }
    if not body.get('commit'):
        return JsonResponse(preview_data)
    if errors or not cards:
        return JsonResponse({**preview_data, 'error': 'Fix the problems listed first; nothing was imported.'}, status=400)
    with transaction.atomic():
        if body.get('replace'):
            project_obj.cards.all().delete()
            start = 0
        else:
            start = (project_obj.cards.aggregate(m=Max('order'))['m'] or 0) + 1
        ProjectCard.objects.bulk_create([
            ProjectCard(project=project_obj, title=c.title, teaser=c.teaser, body=c.body,
                        takeaways_raw=c.takeaways_raw, order=start + i)
            for i, c in enumerate(cards)
        ])
    return JsonResponse({'ok': True, 'created': len(cards)})


@studio_api
@require_GET
def cards_export(request, pk):
    project_obj = get_object_or_404(Projects, pk=pk)
    response = HttpResponse(serialize_cards_to_markdown(project_obj.cards.all()), content_type='text/markdown; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{slugify(project_obj.name) or "article"}-sections.md"'
    return response


# ---------------------------------------------------------------- media (photos, videos, embeds)

def _media_spec(kind):
    if kind not in MEDIA:
        raise Http404
    return MEDIA[kind]


def _media_item(pk, kind, mid):
    return get_object_or_404(_media_spec(kind)['model'], pk=mid, project_id=pk)


def _verified_upload(spec, ref):
    """Cloudinary's signed reference from a direct upload -> a CloudinaryResource, or None if it fails a check.

    The signature proves Cloudinary issued it for this account; the type and folder prove it came
    through this kind's signed upload (so a thumbnail can't be attached as a video, for example)."""
    try:
        resource = DirectUploadField(spec['upload']).clean(str(ref or ''))
    except ValidationError:
        return None
    field = spec['model']._meta.get_field(spec['file'])
    folder = field.options.get('folder', '')
    if not resource or resource.resource_type != field.resource_type:
        return None
    if folder and not str(resource.public_id).startswith(folder + '/'):
        return None
    return resource


@studio_api
@require_POST
def media_sign(request, pk, kind):
    """A short-lived signature for one browser upload, with the folder and transformation fixed by the server."""
    spec = _media_spec(kind)
    if not spec['upload']:
        raise Http404
    get_object_or_404(Projects, pk=pk)
    return JsonResponse(signed_upload_params(spec['upload']))


@studio_api
@require_POST
def media_create(request, pk, kind):
    """Photos and videos: {"ref": <signed reference>, "caption": ""}. Embeds: {"embed_code": "...", "caption": ""}."""
    spec = _media_spec(kind)
    project_obj = get_object_or_404(Projects, pk=pk)
    body = _body(request)
    if body is None:
        return _error('Bad request.')
    order = (getattr(project_obj, kind).aggregate(m=Max('order'))['m'] or 0) + 1
    item = spec['model'](project=project_obj, order=order)
    patch = {'caption': str(body.get('caption', ''))}
    if spec['upload']:
        resource = _verified_upload(spec, body.get('ref'))
        if resource is None:
            return _error('The upload could not be verified. Please upload it again.')
        setattr(item, spec['file'], resource)
    else:
        patch['embed_code'] = str(body.get('embed_code', ''))
    ok, response = _save_patch(item, spec['fields'], patch)
    if not ok:
        return response
    return JsonResponse({'ok': True, 'item': ser_media(kind, item)})


@studio_api
@require_POST
def media_update(request, pk, kind, mid):
    spec = _media_spec(kind)
    item = _media_item(pk, kind, mid)
    patch = _body(request)
    if patch is None:
        return _error('Bad request.')
    ok, response = _save_patch(item, spec['fields'], patch)
    if not ok:
        return response
    return JsonResponse({'ok': True, 'item': ser_media(kind, item)})


@studio_api
@require_POST
def media_delete(request, pk, kind, mid):
    # Only the link to this project is removed. The file stays in Cloudinary, because a blog post's
    # text may still show it by its address.
    _media_item(pk, kind, mid).delete()
    return JsonResponse({'ok': True})


@studio_api
@require_POST
def media_reorder(request, pk, kind):
    spec = _media_spec(kind)
    project_obj = get_object_or_404(Projects, pk=pk)
    ids = (_body(request) or {}).get('ids')
    own = set(getattr(project_obj, kind).values_list('pk', flat=True))
    if not isinstance(ids, list) or set(ids) != own or len(ids) != len(own):
        return _error('Bad order.')
    with transaction.atomic():
        for i, mid in enumerate(ids, 1):
            spec['model'].objects.filter(pk=mid).update(order=i)
    return JsonResponse({'ok': True})
