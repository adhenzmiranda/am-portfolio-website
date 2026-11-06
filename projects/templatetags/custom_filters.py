import re

from django import template
from django.utils.text import Truncator
from ..models import TECH_STACK_CHOICES

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def tech_display(value):
    # Flatten grouped choices
    flat_choices = []
    for group in TECH_STACK_CHOICES:
        flat_choices.extend(group[1])
    return dict(flat_choices).get(value, value)

@register.filter
def one_liner(markdown_text, length=110):
    """First sentence of a markdown description as plain text, for project cards.

    Uses the same markdown-to-text cleanup as the SEO meta descriptions, then
    keeps only the first sentence (cards show a single line).
    """
    from ..views import plain_text_summary  # local import: views imports models, not filters
    text = plain_text_summary(markdown_text, length=1000)
    first = text
    for match in _SENTENCE_END.finditer(text):
        last_word = text[:match.start() + 1].rsplit(' ', 1)[-1].lower()
        if last_word not in _ABBREVIATIONS:
            first = text[:match.start() + 1]
            break
    return Truncator(first).chars(int(length))


# A sentence ends at . ! or ? followed by a space and a capital letter or digit,
# unless the word before is a common abbreviation ("Mr. Khan", "e.g. Unity").
_SENTENCE_END = re.compile(r'[.!?](?=\s+[A-Z0-9"“])')
_ABBREVIATIONS = {'mr.', 'mrs.', 'ms.', 'dr.', 'prof.', 'st.', 'e.g.', 'i.e.', 'etc.', 'vs.', 'no.', 'inc.', 'ltd.', 'co.'}


@register.filter
def cloudinary(url, transformation):
    """Ask Cloudinary for a resized/re-encoded version of an uploaded file.

    `transformation` is a Cloudinary transformation string, optionally followed by
    `|ext` to change the delivered format, e.g.:
        {{ photo.image.url|cloudinary:"w_800,c_limit,q_auto,f_auto" }}
        {{ video.video.url|cloudinary:"so_1,w_640,h_800,c_fill,q_auto|jpg" }}  (video poster frame)
    Non-Cloudinary URLs are returned unchanged.
    """
    url = str(url or '')
    if '/upload/' not in url or 'res.cloudinary.com' not in url:
        return url
    transformation, _, ext = str(transformation).partition('|')
    url = url.replace('/upload/', f'/upload/{transformation}/', 1)
    if ext:
        url = re.sub(r'\.[A-Za-z0-9]+$', f'.{ext}', url)
    return url


# Embed platforms whose player is not 16:9; the template turns the name into a CSS class
# (classes rather than inline styles, so a future Content-Security-Policy can block inline styles).
_EMBED_SHAPES = {
    'itch.io': 'itch',            # itch.io game widget, 552 x 167
    'linkedin.com': 'linkedin',   # LinkedIn post, roughly 504 x 600
}


@register.filter
def embed_shape(src):
    """Shape name for an embed iframe based on where it comes from: 'wide' (16:9) by default."""
    src = str(src or '')
    for host, shape in _EMBED_SHAPES.items():
        if host in src:
            return shape
    return 'wide'
