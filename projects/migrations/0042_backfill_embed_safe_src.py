from html.parser import HTMLParser
from urllib.parse import urlparse

from django.db import migrations

ALLOWED_EMBED_DOMAINS = ['youtube.com', 'vimeo.com', 'instagram.com', 'embed.figma.com', 'itch.io', 'linkedin.com']


class _SingleIframeParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.iframe_count = 0
        self.has_other_tags = False
        self.has_stray_text = False
        self.src = None

    def _handle_tag(self, tag, attrs):
        if tag == 'iframe':
            self.iframe_count += 1
            if self.src is None:
                self.src = dict(attrs).get('src')
        else:
            self.has_other_tags = True

    def handle_starttag(self, tag, attrs):
        self._handle_tag(tag, attrs)

    def handle_startendtag(self, tag, attrs):
        self._handle_tag(tag, attrs)

    def handle_endtag(self, tag):
        if tag != 'iframe':
            self.has_other_tags = True

    def handle_data(self, data):
        if data.strip():
            self.has_stray_text = True


def extract_safe_src(embed_code):
    """Re-run the new strict embed validation against existing data. Returns
    the cleaned src if it passes, or None if it doesn't (e.g. it relied on
    the old substring-match check, like 'youtube.com.evil.com')."""
    parser = _SingleIframeParser()
    try:
        parser.feed(embed_code or '')
        parser.close()
    except Exception:
        return None

    if parser.iframe_count != 1 or parser.has_other_tags or parser.has_stray_text or not parser.src:
        return None

    parsed_src = urlparse(parser.src)
    if parsed_src.scheme != 'https':
        return None

    hostname = (parsed_src.hostname or '').lower()
    is_allowed = any(
        hostname == domain or hostname.endswith('.' + domain)
        for domain in ALLOWED_EMBED_DOMAINS
    )
    return parser.src if is_allowed else None


def backfill_safe_src(apps, schema_editor):
    ProjectEmbed = apps.get_model('projects', 'ProjectEmbed')
    for embed in ProjectEmbed.objects.all():
        safe_src = extract_safe_src(embed.embed_code)
        embed.safe_src = safe_src or ''
        embed.is_safe = bool(safe_src)
        embed.save(update_fields=['safe_src', 'is_safe'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0041_projectembed_safe_src'),
    ]

    operations = [
        migrations.RunPython(backfill_safe_src, noop_reverse),
    ]
