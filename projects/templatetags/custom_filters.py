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
