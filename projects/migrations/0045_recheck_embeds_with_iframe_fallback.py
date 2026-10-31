from html.parser import HTMLParser
from urllib.parse import urlparse

from django.db import migrations

ALLOWED_EMBED_DOMAINS = ['youtube.com', 'vimeo.com', 'instagram.com', 'embed.figma.com', 'itch.io', 'linkedin.com']


class _SingleIframeParser(HTMLParser):
    """Same as 0042, but fallback content inside the <iframe> (itch.io puts an
    <a> link there) is ignored instead of rejecting the whole embed."""

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


def extract_safe_src(embed_code):
    """Re-run the embed validation (with the iframe-fallback fix) against existing data. Returns
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


def recheck_embeds(apps, schema_editor):
    ProjectEmbed = apps.get_model('projects', 'ProjectEmbed')
    for embed in ProjectEmbed.objects.filter(is_safe=False):
        safe_src = extract_safe_src(embed.embed_code)
        if safe_src:
            embed.safe_src = safe_src
            embed.is_safe = True
            embed.save(update_fields=['safe_src', 'is_safe'])


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0044_seed_experience_education'),
    ]

    operations = [
        migrations.RunPython(recheck_embeds, migrations.RunPython.noop),
    ]
