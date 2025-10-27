from django.db import models
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

class Projects(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    year = models.IntegerField(default=2024)
    featured = models.BooleanField(default=False, help_text="Show this project in the Featured Projects section.")
    category = models.CharField(
        max_length=50, 
        choices=[
            ('Web Development', 'Web Development'),
            ('Mobile Development', 'Mobile Development'),
            ('Data Science', 'Data Science'),
            ('Machine Learning', 'Machine Learning'),
            ('Game Development', 'Game Development'),
            ('Graphic Design', 'Graphic Design'),
            ('Website Design', 'Website Design'),
            ('Application Development', 'Application Development'),
            ('Application Concept', 'Application Concept'),
            ('Other', 'Other')
        ],
        default='Other'
    )
    tags = models.CharField(max_length=100, blank=True)
    # Removed main_image for clarity. Only using one image field now.
    thumbnail_image = CloudinaryField('image', folder='thumbnails', blank=True, null=True,
        transformation=[
            {'width': 600, 'height': 338, 'crop': 'fill'},
            {'quality': 'auto', 'fetch_format': 'auto'}
        ])
    technologies = MultiSelectField(choices=TECH_STACK_CHOICES, blank=True, max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name + ' - ' + str(self.description)[:20] + '...'

    def get_technology_display(self, tech_value):
        # Flatten grouped choices for lookup
        flat_choices = []
        for group in TECH_STACK_CHOICES:
            flat_choices.extend(group[1])
        return dict(flat_choices).get(tech_value, tech_value)

class ProjectPhoto(models.Model):
    project = models.ForeignKey(Projects, on_delete=models.CASCADE, related_name='photos')
    from django.core.exceptions import ValidationError
    import os
    def validate_image_file(value):
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

class ProjectEmbed(models.Model):
    project = models.ForeignKey(Projects, on_delete=models.CASCADE, related_name='embeds')
    embed_code = models.TextField(
        help_text="Paste the full embed code (e.g., <iframe ...></iframe>) for a video or interactive media. Example: <iframe width='560' height='315' src='https://www.youtube.com/embed/VIDEO_ID' frameborder='0' allowfullscreen></iframe>"
    )
    is_safe = models.BooleanField(default=False, editable=False)
    caption = models.CharField(max_length=200, blank=True)  # <-- Add this line
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'created_at']

    def __str__(self):
        return f"Embed for {self.project.name} ({self.id})"

    def clean(self):
        from django.core.exceptions import ValidationError
        allowed_sources = ['youtube.com', 'vimeo.com', 'instagram.com', 'embed.figma.com', 'itch.io']
        code = self.embed_code.lower()
        if '<iframe' not in code:
            self.is_safe = False
            raise ValidationError('Only iframe embeds are allowed.')
        has_allowed = any(source in code for source in allowed_sources)
        if not has_allowed:
            self.is_safe = False
            raise ValidationError(f'Only embeds from {", ".join(allowed_sources)} are allowed.')
        self.is_safe = True