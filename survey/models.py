"""
The survey builder (edited in the admin) and the responses.

Survey ─┬─ Section (pages, in order) ── Question (on "questions" pages)
        ├─ Prompt  ("Would you send this?" items, shown before and after the media)
        ├─ Condition (the randomised media groups: video, infographic, text post...)
        └─ Participant (one person's response)

Everything participants see is locked once a survey has responses, so every
response in a dataset answered exactly the same survey (see is_locked).
"""
import uuid

from cloudinary.models import CloudinaryField
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

# Paths already used by the site; a survey can't take them.
RESERVED_SLUGS = {
    'about', 'admin', 'admin-dev', 'api', 'contact', 'llms', 'media', 'preview-error',
    'projects', 'robots', 'sitemap', 'static', 'survey',
}

BUILTIN_MOCKS = [
    ('', 'None'),
    ('formFilled', 'Visa form, filled in'),
    ('formBlank', 'Visa form, blank'),
    ('slide', 'Lecture slide'),
    ('chat', 'Group chat'),
    ('bank', 'Banking app error'),
    ('memory', 'Chatbot saved memories'),
]


def validate_slug_not_reserved(value):
    if value.lower() in RESERVED_SLUGS:
        raise ValidationError(f'"{value}" is already used by the site. Pick another address.')


def lines(text):
    """Non-empty lines of a textarea, stripped."""
    return [line.strip() for line in (text or '').splitlines() if line.strip()]


class Survey(models.Model):
    DRAFT, OPEN, CLOSED = 'draft', 'open', 'closed'
    STATUS_CHOICES = [
        (DRAFT, 'Draft: only you can preview it'),
        (OPEN, 'Open: accepting responses'),
        (CLOSED, 'Closed: not accepting responses'),
    ]

    title = models.CharField(max_length=200)
    slug = models.SlugField(
        'Address', max_length=60, unique=True, validators=[validate_slug_not_reserved],
        help_text='The survey lives at adhenzmiranda.com/<address>/. Keep it short for QR codes, e.g. msc-survey.',
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=DRAFT)
    version = models.PositiveIntegerField(default=1, help_text='Saved on every response. Duplicating a survey makes the next version.')
    batch = models.CharField(
        max_length=40, default='main',
        help_text='Saved on every response, so you can tell rounds apart: e.g. "pilot" first, then "main".',
    )
    target_responses = models.PositiveIntegerField(default=160, help_text='Completed responses you are aiming for (all groups together).')

    # Consent (first page)
    intro_heading = models.CharField('Heading', max_length=200)
    intro_text = models.TextField('Information', help_text='Markdown: ### for headings, - for bullet points.')
    consent_statements = models.TextField(help_text='One per line. Each becomes a tick box; all must be ticked to start.')
    start_label = models.CharField('Start button', max_length=60, default='I agree, start the survey')
    researcher_email = models.EmailField(blank=True, help_text='Shown on the consent page. Required to open the survey.')
    ethics_contact = models.CharField(
        max_length=200, blank=True,
        help_text='Supervisor or ethics contact shown on the consent page (an email address or a name and email). Required to open the survey.',
    )
    ethics_reference = models.CharField(
        max_length=100, blank=True,
        help_text='Ethics approval reference. Not shown to participants, but required to open the survey.',
    )

    # Closed page
    closed_heading = models.CharField(max_length=200, default='This survey is closed')
    closed_message = models.TextField(default="It's no longer accepting responses. Thanks for your interest.")

    # Thank-you page
    thanks_heading = models.CharField(max_length=200, default="Thanks, you're done")
    thanks_message = models.TextField(blank=True, help_text='Markdown.')
    share_image = CloudinaryField(
        'image', folder='survey', blank=True, null=True,
        help_text='Optional image people can share or save (e.g. 1080 x 1920 for stories). '
                  'Keep the tips and answers off it, so friends who take the survey later are not primed.',
    )
    share_text = models.CharField(
        max_length=280, blank=True,
        default='I just took a 10-minute survey about AI chatbots for an MSc dissertation. Take it too:',
        help_text='Text that goes with the link when someone taps Share.',
    )
    already_done_message = models.CharField(max_length=200, default="You've already taken part, thank you!")

    # Look of the mock social posts
    post_handle = models.CharField(max_length=60, default='campuscybertips', help_text='Account name shown on the media posts.')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} (v{self.version})'

    def get_absolute_url(self):
        return f'/{self.slug}/'

    @property
    def is_locked(self):
        """Locked once anyone has started it: editing then would mean people answered different surveys."""
        return self.pk is not None and self.participants.exists()

    def consent_list(self):
        return lines(self.consent_statements)

    def question_list(self):
        return list(Question.objects.filter(section__survey=self).select_related('section').order_by('section__order', 'section__id', 'order', 'id'))

    def structure_problems(self):
        """Everything that must be fixed before the survey can open (empty list = ready)."""
        problems = []
        sections = list(self.sections.all())
        kinds = [s.kind for s in sections]
        for kind, label in [(Section.TASK_BEFORE, '"Would you send this?" (before)'),
                            (Section.MEDIA, 'Random media'),
                            (Section.TASK_AFTER, '"Would you send this?" (after)')]:
            if kinds.count(kind) != 1:
                problems.append(f'Add exactly one {label} page (there are {kinds.count(kind)}).')
        if all(kinds.count(k) == 1 for k in (Section.TASK_BEFORE, Section.MEDIA, Section.TASK_AFTER)):
            if not kinds.index(Section.TASK_BEFORE) < kinds.index(Section.MEDIA) < kinds.index(Section.TASK_AFTER):
                problems.append('Page order must be: "before" task, then random media, then "after" task.')
        if not self.prompts.exists():
            problems.append('Add at least one prompt for the "Would you send this?" task.')
        conditions = [c for c in self.conditions.all() if c.active]
        if len(conditions) < 2:
            problems.append('Turn on at least two random media groups.')
        for c in conditions:
            if not c.has_media():
                problems.append(f'Media group "{c.name}" has no {c.get_kind_display().lower()} yet.')
        codes = [q.code for q in self.question_list()]
        for code in sorted({c for c in codes if codes.count(c) > 1}):
            problems.append(f'Question code "{code}" is used more than once.')
        for q in self.question_list():
            if q.kind in Question.OPTION_KINDS and not q.option_list():
                problems.append(f'Question "{q.code}" needs at least one option.')
        if not self.consent_list():
            problems.append('Add at least one consent statement.')
        return problems

    def open_problems(self):
        problems = self.structure_problems()
        if not self.researcher_email:
            problems.append('Fill in the researcher email.')
        if not self.ethics_contact:
            problems.append('Fill in the supervisor or ethics contact.')
        if not self.ethics_reference:
            problems.append('Fill in the ethics approval reference.')
        return problems

    def clean(self):
        if self.status == self.OPEN and self.pk:
            problems = self.open_problems()
            if problems:
                raise ValidationError({'status': ['Not ready to open yet:'] + problems})


class Section(models.Model):
    INFO, QUESTIONS, TASK_BEFORE, MEDIA, TASK_AFTER = 'info', 'questions', 'task_before', 'media', 'task_after'
    KIND_CHOICES = [
        (QUESTIONS, 'Questions'),
        (INFO, 'Text only'),
        (TASK_BEFORE, '"Would you send this?" task (before)'),
        (MEDIA, 'Random media (one group per person)'),
        (TASK_AFTER, '"Would you send this?" task (after)'),
    ]

    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='sections')
    order = models.PositiveIntegerField(default=0, help_text='Lower numbers come first.')
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=QUESTIONS)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, help_text='Optional text under the title. Markdown.')
    button_label = models.CharField(max_length=60, blank=True, help_text='Leave blank for "Next" (or "Submit answers" on the last page).')

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f'{self.order}. {self.title} ({self.get_kind_display()})'


class Question(models.Model):
    SHORT_TEXT, LONG_TEXT, NUMBER, CHOICE, DROPDOWN, CHECKBOXES, SCALE = (
        'short_text', 'long_text', 'number', 'choice', 'dropdown', 'checkboxes', 'scale')
    KIND_CHOICES = [
        (CHOICE, 'Multiple choice (pick one)'),
        (CHECKBOXES, 'Checkboxes (pick any)'),
        (DROPDOWN, 'Dropdown'),
        (SCALE, 'Scale 1 to 5'),
        (SHORT_TEXT, 'Short answer'),
        (LONG_TEXT, 'Paragraph'),
        (NUMBER, 'Number'),
    ]
    OPTION_KINDS = {CHOICE, CHECKBOXES, DROPDOWN}
    SHORT_MAX, LONG_MAX = 200, 2000

    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name='questions')
    order = models.PositiveIntegerField(default=0)
    code = models.SlugField(
        max_length=40, help_text='Column name in the CSV, e.g. age or rating_1_engagement. Unique within the survey.')
    text = models.CharField(max_length=300)
    help_text = models.CharField(max_length=300, blank=True)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=CHOICE)
    required = models.BooleanField(default=True)
    options = models.TextField(blank=True, help_text='For multiple choice, checkboxes and dropdowns: one option per line.')
    min_value = models.IntegerField(null=True, blank=True, help_text='Number questions only.')
    max_value = models.IntegerField(null=True, blank=True, help_text='Number questions only.')
    range_message = models.CharField(
        max_length=200, blank=True, help_text='Shown when a number is out of range, e.g. "This survey is for students aged 18 or older."')
    scale_low_label = models.CharField(max_length=60, default='Strongly disagree', blank=True)
    scale_high_label = models.CharField(max_length=60, default='Strongly agree', blank=True)
    construct = models.SlugField(
        max_length=40, blank=True,
        help_text='Hidden from participants. Groups scale questions for analysis (e.g. engagement); the CSV gets a mean per group.')
    attention_answer = models.CharField(
        max_length=200, blank=True,
        help_text='Attention check: the answer a careful reader gives. The CSV marks whether each person passed. Leave blank for normal questions.')

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f'{self.code}: {self.text}'

    def option_list(self):
        return lines(self.options)


class Prompt(models.Model):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='prompts')
    number = models.PositiveSmallIntegerField(help_text='1, 2, 3... Matches your dissertation tables and the CSV columns.')
    text = models.TextField('Message', help_text='What the student would send to the chatbot.')
    screenshot = CloudinaryField('image', folder='survey', blank=True, null=True, help_text='Screenshot attached to the message (use fictional details).')
    builtin_mock = models.CharField(
        'Built-in screenshot', max_length=20, choices=BUILTIN_MOCKS, blank=True,
        help_text='Used when no screenshot is uploaded.')
    context_image = CloudinaryField(
        'image', folder='survey', blank=True, null=True,
        help_text='Optional: shown above the message, e.g. what the chatbot already remembers.')
    context_mock = models.CharField('Built-in context', max_length=20, choices=BUILTIN_MOCKS, blank=True)
    context_label = models.CharField(max_length=120, blank=True, default='What this chatbot already remembers about you')
    risky = models.BooleanField(
        default=False,
        help_text='Answer key. Risky: "Change it first" or "Wouldn\'t send" is correct. Safe: "Send as is" is correct.')
    pair_group = models.CharField(
        max_length=20, blank=True,
        help_text='Prompts with the same group letter (e.g. A) are never shown next to each other.')

    class Meta:
        ordering = ['number']
        constraints = [models.UniqueConstraint(fields=['survey', 'number'], name='survey_prompt_number_unique')]

    def __str__(self):
        return f'Prompt {self.number}'


class Condition(models.Model):
    VIDEO, IMAGE, TEXT = 'video', 'image', 'text'
    KIND_CHOICES = [(VIDEO, 'Video (reel)'), (IMAGE, 'Image (infographic or post)'), (TEXT, 'Text post')]

    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='conditions')
    key = models.SlugField(max_length=20, help_text='Short id saved on each response, e.g. video, infographic, text.')
    name = models.CharField(max_length=60, help_text='e.g. Short-form video')
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    video = CloudinaryField('video', resource_type='video', folder='survey', blank=True, null=True)
    image = CloudinaryField(
        'image', folder='survey', blank=True, null=True,
        help_text='The infographic or post image. For a video, an optional still shown while it loads.')
    text_body = models.TextField(blank=True, help_text='Text posts: the post itself. A blank line starts a new paragraph.')
    caption = models.TextField(blank=True, help_text='Caption under the post (optional).')
    alt_text = models.TextField(
        blank=True, help_text='Images: describe everything the image says, for screen readers (usually the full script).')
    active = models.BooleanField(default=True, help_text='Only active groups are assigned.')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']
        constraints = [models.UniqueConstraint(fields=['survey', 'key'], name='survey_condition_key_unique')]

    def __str__(self):
        return self.name

    def has_media(self):
        if self.kind == self.VIDEO:
            return bool(self.video)
        if self.kind == self.IMAGE:
            return bool(self.image)
        return bool(self.text_body.strip())


class Participant(models.Model):
    """One person's response.

    Created when both consent boxes are ticked (so drop-outs per group can be
    counted) and filled in on submit. Never add anything that identifies a
    person: no name, email, student ID, IP address, user agent or cookies.
    """
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    survey = models.ForeignKey(Survey, on_delete=models.PROTECT, related_name='participants')
    survey_version = models.PositiveIntegerField()
    batch = models.CharField(max_length=40, db_index=True)
    condition = models.ForeignKey(Condition, on_delete=models.PROTECT, related_name='participants')
    source = models.CharField(max_length=60, blank=True, help_text='Recruitment link tag (?src=...), e.g. rak-poster.')
    started_at = models.DateTimeField(default=timezone.now, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True, db_index=True)

    answers = models.JSONField(default=dict, blank=True, help_text='{question code: answer}')
    before_order = models.JSONField(default=list, blank=True)
    after_order = models.JSONField(default=list, blank=True)
    before_answers = models.JSONField(default=dict, blank=True, help_text='{prompt number: choice}')
    after_answers = models.JSONField(default=dict, blank=True)
    before_score = models.PositiveSmallIntegerField(null=True, blank=True)
    after_score = models.PositiveSmallIntegerField(null=True, blank=True)
    score_change = models.SmallIntegerField(null=True, blank=True)

    message_seconds = models.FloatField(null=True, blank=True, validators=[MinValueValidator(0)])
    video_watched_seconds = models.FloatField(null=True, blank=True)
    video_finished = models.BooleanField(null=True, blank=True)
    total_seconds = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f'Response {self.pk}'

    @property
    def completed(self):
        return self.completed_at is not None
