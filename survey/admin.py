import io
from datetime import date

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import path, reverse
from django.utils.html import format_html, format_html_join

from projects.direct_upload import DirectUploadField, sign_upload

from .export import SurveyExport
from .logic import progress
from .models import Condition, Participant, Prompt, Question, Section, Survey

# Fields participants see while answering. Frozen once a survey has responses.
LOCKED_SURVEY_FIELDS = ('title', 'intro_heading', 'intro_text', 'consent_statements', 'start_label', 'post_handle')


# ---------------------------------------------------------------- Inlines

class LockedWhenAnsweredMixin:
    """Inlines become read-only once the parent survey has responses."""

    def _survey(self, obj):
        return obj.survey if isinstance(obj, Section) else obj

    def _locked(self, obj):
        survey = self._survey(obj)
        return survey is not None and survey.is_locked

    def has_add_permission(self, request, obj=None):
        return not self._locked(obj) and super().has_add_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        return not self._locked(obj) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return not self._locked(obj) and super().has_delete_permission(request, obj)


class SectionInline(LockedWhenAnsweredMixin, admin.TabularInline):
    model = Section
    extra = 0
    fields = ('order', 'kind', 'title', 'button_label', 'question_count')
    readonly_fields = ('question_count',)
    show_change_link = True

    @admin.display(description='Questions')
    def question_count(self, obj):
        if obj.pk and obj.kind == Section.QUESTIONS:
            return obj.questions.count()
        return '-'


class PromptInline(LockedWhenAnsweredMixin, admin.StackedInline):
    model = Prompt
    extra = 0
    fields = (('number', 'risky', 'pair_group'), 'text', ('screenshot', 'builtin_mock'),
              'context_label', ('context_image', 'context_mock'))


class ConditionForm(forms.ModelForm):
    # Videos go straight from the browser to Cloudinary (projects/direct_upload.py),
    # so a big reel can't hit Heroku's 30 second limit.
    video = DirectUploadField(
        'survey_video', label='Video',
        help_text='Uploads straight to Cloudinary when you choose a file; wait for "Uploaded", then Save. '
                  'Vertical (9:16) mp4 with burned-in captions, up to 100 MB.',
    )

    class Meta:
        model = Condition
        fields = '__all__'

    def clean_video(self):
        value = self.cleaned_data.get('video')
        if value is None and self.instance.pk:
            return self.instance.video   # nothing new chosen: keep the current video
        return value


class ConditionInline(LockedWhenAnsweredMixin, admin.StackedInline):
    model = Condition
    form = ConditionForm
    extra = 0
    fields = (('key', 'name', 'kind', 'active', 'order'), 'video', 'image', 'text_body', 'caption', 'alt_text',
              'media_preview')
    readonly_fields = ('media_preview',)

    @admin.display(description='Current media')
    def media_preview(self, obj):
        if obj.pk and obj.kind == Condition.VIDEO and obj.video:
            return format_html('<video src="{}" width="160" controls muted playsinline preload="metadata"></video>', obj.video.url)
        if obj.pk and obj.image:
            return format_html('<img src="{}" style="max-width:160px;max-height:200px">', obj.image.url)
        return '-'


class QuestionInline(LockedWhenAnsweredMixin, admin.StackedInline):
    model = Question
    extra = 0
    fields = (('order', 'code', 'kind', 'required'), 'text', 'help_text', 'options',
              ('min_value', 'max_value', 'range_message'), ('scale_low_label', 'scale_high_label'),
              ('construct', 'attention_answer'))


# ---------------------------------------------------------------- Survey

@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    list_display = ('title', 'address', 'status', 'version', 'batch', 'completed_count', 'updated_at')
    list_filter = ('status',)
    inlines = [SectionInline, PromptInline, ConditionInline]
    actions = ['duplicate']
    readonly_fields = ('version', 'links', 'progress', 'checklist')
    fieldsets = (
        (None, {'fields': ('title', 'slug', 'status', 'links', 'checklist', 'progress')}),
        ('Data collection', {'fields': ('batch', 'target_responses', 'version', 'ethics_reference')}),
        ('Consent page', {'fields': ('intro_heading', 'intro_text', 'consent_statements', 'start_label',
                                     'researcher_email', 'ethics_contact')}),
        ('Closed page', {'fields': ('closed_heading', 'closed_message')}),
        ('Thank-you page', {'fields': ('thanks_heading', 'thanks_message', 'share_image', 'share_text',
                                       'already_done_message')}),
        ('Media posts', {'fields': ('post_handle',)}),
    )

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj is not None and obj.is_locked:
            fields += LOCKED_SURVEY_FIELDS
        return fields

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _completed=Count('participants', filter=Q(participants__completed_at__isnull=False)))

    @admin.display(description='Address')
    def address(self, obj):
        return f'/{obj.slug}/'

    @admin.display(description='Completed', ordering='_completed')
    def completed_count(self, obj):
        return obj._completed

    # ---- read-only panels on the edit page

    @admin.display(description='Links')
    def links(self, obj):
        if not obj.pk:
            return 'Save first.'
        from .views import review_url
        live = f'{settings.SITE_URL}/{obj.slug}/'
        qr = reverse('admin:survey_survey_qr', args=[obj.pk])
        export = reverse('admin:survey_survey_export', args=[obj.pk])
        lock_note = (format_html('<p><strong>Locked:</strong> this survey has responses, so the questions, prompts, '
                                 'media and consent text can no longer change. To change them, use the '
                                 '"Duplicate as a new version" action.</p>') if obj.is_locked else '')
        return format_html(
            '{lock}'
            '<p>Public link: <a href="{live}" target="_blank" rel="noopener">{live}</a></p>'
            '<p>Review link (supervisor; no login, nothing saved): <a href="{review}" target="_blank" rel="noopener">{review}</a></p>'
            '<p><a class="button" href="/{slug}/edit/" style="background:#2436BC;color:#fff">Open the editor</a> '
            '<a class="button" href="/{slug}/?preview=1" target="_blank" rel="noopener">Preview (nothing is saved)</a></p>'
            '<p>QR code for '
            '<input type="text" id="qr-src" placeholder="optional tag, e.g. rak-poster" style="width:16em" '
            'pattern="[a-z0-9_-]*">: '
            '<a href="{qr}?format=png" onclick="this.href=\'{qr}?format=png&src=\'+encodeURIComponent(document.getElementById(\'qr-src\').value)">PNG</a> | '
            '<a href="{qr}?format=svg" onclick="this.href=\'{qr}?format=svg&src=\'+encodeURIComponent(document.getElementById(\'qr-src\').value)">SVG</a>'
            '<br><small>A tag adds ?src=tag to the link, so the CSV shows where each person came from.</small></p>'
            '<p>Responses as CSV: <a href="{export}?completed=1">completed only</a> | '
            '<a href="{export}">everyone, including drop-outs</a></p>',
            lock=lock_note, live=live, review=review_url(obj), slug=obj.slug, qr=qr, export=export,
        )

    @admin.display(description='Ready to open?')
    def checklist(self, obj):
        if not obj.pk:
            return '-'
        problems = obj.open_problems()
        if not problems:
            return format_html('<span style="color:#2e7d32">All set. Change Status to Open when you are ready.</span>')
        return format_html('<ul style="margin:0;padding-left:1.2em">{}</ul>',
                           format_html_join('', '<li>{}</li>', ((p,) for p in problems)))

    @admin.display(description='Progress (current batch)')
    def progress(self, obj):
        if not obj.pk:
            return '-'
        p = progress(obj)
        table = format_html_join('', '<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>',
                                 ((g['name'], g['completed'], g['active'], g['dropped']) for g in p['groups']))
        return format_html(
            '<p><strong>{total}</strong> of {target} completed ({pct}%) in batch "{batch}".</p>'
            '<table><thead><tr><th>Group</th><th>Completed</th><th>In progress</th><th>Dropped out</th></tr></thead>'
            '<tbody>{table}</tbody></table>',
            total=p['completed'], target=p['target'], pct=p['percent'], batch=p['batch'],
            table=table or format_html('<tr><td colspan="4">No responses yet.</td></tr>'),
        )

    # ---- extra admin pages

    def get_urls(self):
        view = self.admin_site.admin_view   # login + 2FA
        return [
            path('sign-video/', view(sign_upload(self, 'survey_video')), name='survey_condition_sign_upload'),
            path('<int:pk>/qr/', view(self.qr_view), name='survey_survey_qr'),
            path('<int:pk>/export/', view(self.export_view), name='survey_survey_export'),
        ] + super().get_urls()

    def qr_view(self, request, pk):
        import segno
        from .validation import clean_source

        survey = get_object_or_404(Survey, pk=pk)
        url = f'{settings.SITE_URL}/{survey.slug}/'
        src = clean_source(request.GET.get('src', ''))
        if src:
            url += f'?src={src}'
        kind = 'svg' if request.GET.get('format') == 'svg' else 'png'
        buffer = io.BytesIO()
        segno.make(url, error='m').save(buffer, kind=kind, scale=12, border=3)
        response = HttpResponse(buffer.getvalue(), content_type='image/svg+xml' if kind == 'svg' else 'image/png')
        name = f'qr_{survey.slug}{"_" + src if src else ""}.{kind}'
        response['Content-Disposition'] = f'attachment; filename="{name}"'
        return response

    def export_view(self, request, pk):
        if not self.has_view_permission(request):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        survey = get_object_or_404(Survey, pk=pk)
        participants = survey.participants.select_related('condition').order_by('started_at')
        if request.GET.get('completed'):
            participants = participants.filter(completed_at__isnull=False)
        return csv_response(survey, participants)

    # ---- actions

    @admin.action(description='Duplicate as a new version (draft, to edit freely)')
    def duplicate(self, request, queryset):
        for survey in queryset:
            copy = duplicate_survey(survey)
            self.message_user(request, format_html(
                'Created <a href="{}">{}</a> at /{}/ as a draft. When you are ready to switch, close the old one and '
                'swap the addresses.', reverse('admin:survey_survey_change', args=[copy.pk]), copy, copy.slug),
                messages.SUCCESS)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.status == Survey.OPEN and obj.open_problems():
            # Pages, prompts or media edited in this same save broke something.
            obj.status = Survey.DRAFT
            obj.save(update_fields=['status'])
            self.message_user(request, 'Set back to Draft: fix the "Ready to open?" list first.', messages.WARNING)


@transaction.atomic
def duplicate_survey(survey):
    sections = list(survey.sections.prefetch_related('questions'))
    prompts = list(survey.prompts.all())
    conditions = list(survey.conditions.all())

    base = f'{survey.slug}-v{survey.version + 1}'
    slug, n = base, 2
    while Survey.objects.filter(slug=slug).exists():
        slug, n = f'{base}-{n}', n + 1

    copy = Survey.objects.get(pk=survey.pk)
    copy.pk = None
    copy.slug = slug
    copy.status = Survey.DRAFT
    copy.version = survey.version + 1
    copy.save()
    for section in sections:
        questions = list(section.questions.all())
        section.pk, section.survey = None, copy
        section.save()
        for q in questions:
            q.pk, q.section = None, section
            q.save()
    for item in prompts + conditions:
        item.pk, item.survey = None, copy
        item.save()
    return copy


def csv_response(survey, participants):
    content = SurveyExport(survey).to_csv(participants)
    response = HttpResponse(content, content_type='text/csv; charset=utf-8')
    name = f'survey_responses_{survey.slug}_{date.today():%Y-%m-%d}.csv'
    response['Content-Disposition'] = f'attachment; filename="{name}"'
    return response


# ---------------------------------------------------------------- Sections

@admin.register(Section)
class SectionAdmin(LockedWhenAnsweredMixin, admin.ModelAdmin):
    """Reached from a survey's page list ("Change"), where its questions are edited."""
    list_display = ('title', 'survey', 'kind', 'order')
    inlines = [QuestionInline]
    fields = ('survey', 'order', 'kind', 'title', 'description', 'button_label')

    def has_module_permission(self, request):
        return False   # hidden from the admin index; open sections from their survey

    def get_readonly_fields(self, request, obj=None):
        return ('survey',) if obj else ()

    def has_add_permission(self, request, obj=None):
        return admin.ModelAdmin.has_add_permission(self, request)

    def response_change(self, request, obj):
        if '_continue' not in request.POST and '_addanother' not in request.POST:
            return redirect('admin:survey_survey_change', obj.survey_id)
        return super().response_change(request, obj)


# ---------------------------------------------------------------- Responses

class CompletedFilter(admin.SimpleListFilter):
    title = 'completed'
    parameter_name = 'completed'

    def lookups(self, request, model_admin):
        return [('yes', 'Completed'), ('no', 'Started, not finished')]

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(completed_at__isnull=False)
        if self.value() == 'no':
            return queryset.filter(completed_at__isnull=True)
        return queryset


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    """Read-only: responses can be viewed, exported and deleted, never edited."""
    list_display = ('id', 'survey', 'condition', 'batch', 'source', 'is_completed', 'before_score',
                    'after_score', 'score_change', 'started_at')
    list_filter = ('survey', CompletedFilter, 'condition__key', 'batch', 'source')
    actions = ['export_csv']
    list_select_related = ('survey', 'condition')

    @admin.display(boolean=True, description='Completed', ordering='completed_at')
    def is_completed(self, obj):
        return obj.completed

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.action(description='Download selected as CSV')
    def export_csv(self, request, queryset):
        surveys = set(queryset.values_list('survey', flat=True))
        if len(surveys) != 1:
            self.message_user(request, 'Pick responses from one survey at a time (use the survey filter).', messages.ERROR)
            return None
        survey = Survey.objects.get(pk=surveys.pop())
        return csv_response(survey, queryset.select_related('condition').order_by('started_at'))
