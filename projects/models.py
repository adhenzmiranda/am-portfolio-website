import os
from html.parser import HTMLParser
from urllib.parse import urlparse
from django.db import models
from django.urls import reverse
from django.core.exceptions import ValidationError
from cloudinary.models import CloudinaryField
from multiselectfield import MultiSelectField
from .fields import CompressedVideoField

TECH_STACK_CHOICES = [
    ('Languages', [
        ('python', 'Python'),
        ('javascript', 'JavaScript'),
        ('html', 'HTML'),
        ('csharp', 'C#'),
        ('kotlin', 'Kotlin'),
    ]),
    ('Frameworks & Libraries', [
        ('scss', 'Sass'),
        ('django', 'Django'),
        ('gsap', 'GSAP'),
        ('cloudinary', 'Cloudinary'),
        ('nodejs', 'Node.js'),
        ('imgur', 'Imgur'),
    ]),
    ('Development Tools', [
        ('github', 'GitHub'),
        ('heroku', 'Heroku'),
        ('androidstudio', 'Android Studio'),
        ('cursor', 'Cursor'),
        ('windsurf', 'Windsurf'),
    ]),
    ('AI & Security Tools', [
        ('chatgpt', 'ChatGPT'),
        ('claude', 'Claude'),
        ('autopsy', 'Autopsy'),
        ('cisco', 'Cisco'),
        ('tryhackme', 'TryHackMe'),
        ('deepseek', 'DeepSeek'),
    ]),
    ('Design & Creative', [
        ('figma', 'Figma'),
        ('photoshop', 'Photoshop'),
        ('illustrator', 'Illustrator'),
        ('lightroom', 'Lightroom'),
        ('canva', 'Canva'),
        ('makeymakey', 'Makey Makey'),
    ]),
    ('Video & Audio', [
        ('premiere', 'Premiere Pro'),
        ('aftereffects', 'After Effects'),
        ('audition', 'Audition'),
        ('davinci', 'DaVinci Resolve'),
        ('filmora', 'Wondershare Filmora'),
    ]),
    ('Game Development', [
        ('unity', 'Unity'),
        ('twine', 'Twine'),
        ('harlowe', 'Harlowe'),
        ('bitsy', 'Bitsy'),
    ]),
]

class Category(models.Model):
    name = models.CharField(max_length=50, unique=True)
    
    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['name']
    
    def __str__(self):
        return self.name

class Projects(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField()
    year = models.IntegerField(default=2024)
    featured = models.BooleanField(default=False, help_text="Show this project in the Featured Projects section.")
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Select a category or add a new one in the Category section."
    )
    # Removed main_image for clarity. Only using one image field now.
    thumbnail_image = CloudinaryField('image', folder='thumbnails', blank=True, null=True,
        transformation=[
            {'width': 600, 'height': 338, 'crop': 'fill'},
            {'quality': 'auto', 'fetch_format': 'auto'}
        ])
    technologies = MultiSelectField(choices=TECH_STACK_CHOICES, blank=True, max_length=255)
    display_mode = models.CharField(
        max_length=20,
        choices=[('portfolio', 'Portfolio'), ('blogpost', 'Blog Post')],
        default='portfolio',
        help_text="Portfolio: media shown in separate sections. Blog Post: description is the main content with inline images via markdown."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name + ' - ' + str(self.description)[:20] + '...'

    def get_absolute_url(self):
        return reverse('project_detail', args=[self.id])

class ProjectPhoto(models.Model):
    project = models.ForeignKey(Projects, on_delete=models.CASCADE, related_name='photos')
    
    def validate_image_file(value):
        # Skip validation for existing Cloudinary resources
        if not hasattr(value, 'name'):
            return
        
        valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        ext = os.path.splitext(value.name)[1].lower()
        if ext not in valid_extensions:
            raise ValidationError('Only image files are allowed.')
        if value.size > 50 * 1024 * 1024:
            raise ValidationError('Image file too large (max 50MB).')

    image = CloudinaryField('image', folder='project_photos',
        transformation=[
            {'width': 1920, 'height': 1080, 'crop': 'limit'},
            {'quality': 'auto', 'fetch_format': 'auto'}
        ],
        validators=[validate_image_file]
    )
    caption = models.CharField(max_length=200, blank=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'created_at']

    def __str__(self):
        return f"{self.project.name} - Photo {self.order}"

class ProjectVideo(models.Model):
    project = models.ForeignKey(Projects, on_delete=models.CASCADE, related_name='videos')
    video = CompressedVideoField('video', 
        folder='project_videos',
        resource_type='video',
        # Don't apply transformations during upload - we already compressed the video
        # transformation=[]  # Removed - we handle compression ourselves
    )
    caption = models.CharField(max_length=200, blank=True, 
        help_text="Optional description for the video")
    order = models.IntegerField(default=0,
        help_text="Order in which videos appear (0 = first)")
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Track compression info
    was_compressed = models.BooleanField(default=False, editable=False)
    original_size_mb = models.FloatField(null=True, blank=True, editable=False)
    compressed_size_mb = models.FloatField(null=True, blank=True, editable=False)
    compression_quality = models.CharField(max_length=10, default='high',
        choices=[('high', 'High Quality (1080p)'), ('medium', 'Balanced (720p)'), ('low', 'Fast Upload (480p)')],
        help_text="Quality preset for automatic compression (only used if file > 100MB)")

    class Meta:
        ordering = ['order', 'created_at']

    def __str__(self):
        return f"{self.project.name} - Video {self.order}"

    def clean(self):
        from django.core.exceptions import ValidationError
        # Basic validation only - compression happens in save()
        if hasattr(self.video, 'file') and self.video.file:
            if hasattr(self.video.file, 'size') and self.video.file.size > 500 * 1024 * 1024:  # 500MB hard limit
                raise ValidationError({
                    'video': 'Video file is too large (over 500MB). Please use a smaller file.'
                })
        super().clean()

class ProjectCard(models.Model):
    project = models.ForeignKey(Projects, on_delete=models.CASCADE, related_name='cards')
    title = models.CharField(max_length=100)
    teaser = models.CharField(max_length=200, help_text="One-line summary shown on the collapsed card.")
    body = models.TextField(help_text="Full section content. Supports the same markdown as the article body.")
    takeaways_raw = models.TextField(
        blank=True,
        verbose_name='Takeaways',
        help_text="Key takeaway bullet points, one per line. Leave blank to omit."
    )
    image = CloudinaryField('image', folder='card_images', blank=True, null=True,
        transformation=[
            {'width': 1200, 'height': 675, 'crop': 'fill'},
            {'quality': 'auto', 'fetch_format': 'auto'}
        ])
    visual_placeholder = models.CharField(
        max_length=200,
        blank=True,
        help_text="Placeholder text shown in a dashed box where a diagram/animation will go later."
    )
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'created_at']

    def __str__(self):
        return f"{self.project.name} - Card: {self.title}"

    @property
    def takeaways(self):
        return [line.strip() for line in self.takeaways_raw.splitlines() if line.strip()]

    @property
    def image_url(self):
        return self.image.url if self.image else None

ALLOWED_EMBED_DOMAINS = ['youtube.com', 'vimeo.com', 'instagram.com', 'embed.figma.com', 'itch.io', 'linkedin.com']


class _SingleIframeParser(HTMLParser):
    """
    Walks the pasted embed code and records whether it is exactly one
    <iframe> element and nothing else (no other tags, no non-whitespace
    text) -- so `<iframe></iframe><script>...</script>` is rejected
    instead of silently passing because the string contains "<iframe".

    Fallback content *inside* the iframe (itch.io puts an <a> link there)
    is ignored: browsers never render it, and the template rebuilds the
    iframe from the validated src only, so it is never output.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.iframe_count = 0
        self.has_other_tags = False
        self.has_stray_text = False
        self.src = None
        self.in_iframe = False

    def _handle_tag(self, tag, attrs, opens_element):
        if tag == 'iframe':
            self.iframe_count += 1
            if self.src is None:
                self.src = dict(attrs).get('src')
            self.in_iframe = opens_element
        elif not self.in_iframe:
            self.has_other_tags = True

    def handle_starttag(self, tag, attrs):
        self._handle_tag(tag, attrs, opens_element=True)

    def handle_startendtag(self, tag, attrs):
        self._handle_tag(tag, attrs, opens_element=False)

    def handle_endtag(self, tag):
        if tag == 'iframe':
            self.in_iframe = False
        elif not self.in_iframe:
            self.has_other_tags = True

    def handle_data(self, data):
        if data.strip() and not self.in_iframe:
            self.has_stray_text = True


class ProjectEmbed(models.Model):
    project = models.ForeignKey(Projects, on_delete=models.CASCADE, related_name='embeds')
    embed_code = models.TextField(
        help_text="Paste the full embed code (e.g., <iframe ...></iframe>) for a video or interactive media. Example: <iframe width='560' height='315' src='https://www.youtube.com/embed/VIDEO_ID' frameborder='0' allowfullscreen></iframe>"
    )
    is_safe = models.BooleanField(default=False, editable=False)
    safe_src = models.URLField(blank=True, editable=False,
        help_text="The validated iframe src, extracted from embed_code. Rendered in place of the raw pasted HTML.")
    caption = models.CharField(max_length=200, blank=True)  # <-- Add this line
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'created_at']

    def __str__(self):
        return f"Embed for {self.project.name} ({self.id})"

    def clean(self):
        from django.core.exceptions import ValidationError
        self.is_safe = False
        self.safe_src = ''

        parser = _SingleIframeParser()
        parser.feed(self.embed_code or '')
        parser.close()

        if parser.iframe_count != 1 or parser.has_other_tags or parser.has_stray_text:
            raise ValidationError('Embed code must contain exactly one <iframe> element and nothing else.')

        if not parser.src:
            raise ValidationError('The iframe must have a src attribute.')

        parsed_src = urlparse(parser.src)
        if parsed_src.scheme != 'https':
            raise ValidationError('The iframe src must use https.')

        hostname = (parsed_src.hostname or '').lower()
        is_allowed = any(
            hostname == domain or hostname.endswith('.' + domain)
            for domain in ALLOWED_EMBED_DOMAINS
        )
        if not is_allowed:
            raise ValidationError(f'Only embeds from {", ".join(ALLOWED_EMBED_DOMAINS)} are allowed.')

        self.safe_src = parser.src
        self.is_safe = True

class Experience(models.Model):
    """A role in the About page's Experience section (edited in the admin)."""
    role = models.CharField(max_length=200, help_text="e.g. Content Creator, Photographer & Videographer")
    organisation = models.CharField(max_length=200)
    location = models.CharField(max_length=200, help_text="e.g. Business Bay, Dubai")
    dates = models.CharField(max_length=100, help_text="Shown exactly as typed, e.g. 'Aug 2026 - Nov 2026' or 'Sep 2026 - Present'")
    highlights_raw = models.TextField("Highlights", blank=True, help_text="One bullet point per line.")
    order = models.IntegerField(default=0, help_text="Lower numbers show first.")
    visible = models.BooleanField(default=True, help_text="Untick to hide this role without deleting it.")

    class Meta:
        ordering = ['order', 'id']
        verbose_name_plural = 'Experience'

    def __str__(self):
        return f"{self.role} - {self.organisation}"

    @property
    def highlights(self):
        return [line.strip() for line in self.highlights_raw.splitlines() if line.strip()]


class Education(models.Model):
    """An entry in the Education card under Experience (edited in the admin)."""
    title = models.CharField(max_length=200, help_text="Shown in bold, e.g. MSc in Cybersecurity (part-time, in progress)")
    details = models.CharField(max_length=300, blank=True, help_text="Shown after the title, e.g. Bath Spa University, expected Jan 2027")
    order = models.IntegerField(default=0, help_text="Lower numbers show first.")
    visible = models.BooleanField(default=True, help_text="Untick to hide this entry without deleting it.")

    class Meta:
        ordering = ['order', 'id']
        verbose_name_plural = 'Education'

    def __str__(self):
        return self.title
