"""
Parser for the "Import from Markdown" article section feature.

Sections (ProjectCard rows) are described as fenced blocks using HTML
comment markers, e.g.:

    <!-- CARD -->
    <!-- TITLE: The Dependency -->
    <!-- TEASER: Healthcare runs on a network it does not control. -->
    Body markdown goes here. Supports the same markdown the article
    body already supports (paragraphs, **bold**, tables, ![alt](url) images).

    <!-- TAKEAWAYS -->
    - Point one
    - Point two

    <!-- /CARD -->

HTML comments are the format of choice because chatbots reliably leave
literal marker text untouched even while paraphrasing surrounding prose,
which keeps LLM-generated imports parseable. See
static/docs/ARTICLE_MARKDOWN_TEMPLATE.md for the full spec handed to authors.
"""
import re
from dataclasses import dataclass

TITLE_MAX_LENGTH = 100
TEASER_MAX_LENGTH = 200

CARD_RE = re.compile(r'<!--\s*CARD\s*-->(.*?)<!--\s*/CARD\s*-->', re.DOTALL | re.IGNORECASE)
TITLE_RE = re.compile(r'<!--\s*TITLE:\s*(.*?)-->', re.IGNORECASE)
TEASER_RE = re.compile(r'<!--\s*TEASER:\s*(.*?)-->', re.IGNORECASE)
TAKEAWAYS_SPLIT_RE = re.compile(r'<!--\s*TAKEAWAYS\s*-->', re.IGNORECASE)
BULLET_RE = re.compile(r'^\s*[-*]\s+(.*)$')


@dataclass
class ParsedCard:
    index: int
    title: str = ''
    teaser: str = ''
    body: str = ''
    takeaways_raw: str = ''

    @property
    def word_count(self):
        return len(self.body.split())

    @property
    def takeaway_count(self):
        return len([line for line in self.takeaways_raw.splitlines() if line.strip()])


@dataclass
class ImportError_:
    index: int
    title: str
    message: str


def _strip_marker_lines(text):
    lines = [
        line for line in text.splitlines()
        if not TITLE_RE.search(line) and not TEASER_RE.search(line)
    ]
    return '\n'.join(lines).strip()


def _parse_takeaways(text):
    lines = []
    for raw_line in text.splitlines():
        match = BULLET_RE.match(raw_line)
        if match:
            lines.append(match.group(1).strip())
    return '\n'.join(lines)


def parse_markdown_cards(text):
    """
    Parse an uploaded markdown blob into ProjectCard-shaped data.

    Returns (cards, errors) where cards is a list of ParsedCard for blocks
    that passed validation, and errors is a list of ImportError_ for blocks
    that didn't (including ones omitted from cards).
    """
    if text is None:
        text = ''
    normalized = text.replace('\r\n', '\n').replace('\r', '\n')

    blocks = CARD_RE.findall(normalized)
    cards = []
    errors = []

    if not blocks:
        errors.append(ImportError_(
            index=0,
            title='',
            message='No <!-- CARD --> ... <!-- /CARD --> blocks found. '
                    'Make sure the file follows the template format.',
        ))
        return cards, errors

    for i, block in enumerate(blocks, start=1):
        title_match = TITLE_RE.search(block)
        teaser_match = TEASER_RE.search(block)
        title = title_match.group(1).strip() if title_match else ''
        teaser = teaser_match.group(1).strip() if teaser_match else ''

        takeaways_split = TAKEAWAYS_SPLIT_RE.split(block, maxsplit=1)
        body_source = takeaways_split[0]
        takeaways_source = takeaways_split[1] if len(takeaways_split) > 1 else ''

        body = _strip_marker_lines(body_source)
        takeaways_raw = _parse_takeaways(takeaways_source)

        card_errors = []
        if not title_match:
            card_errors.append('Missing <!-- TITLE: ... --> marker.')
        elif len(title) > TITLE_MAX_LENGTH:
            card_errors.append(f'Title exceeds {TITLE_MAX_LENGTH} characters.')

        if not teaser_match:
            card_errors.append('Missing <!-- TEASER: ... --> marker.')
        elif len(teaser) > TEASER_MAX_LENGTH:
            card_errors.append(f'Teaser exceeds {TEASER_MAX_LENGTH} characters.')

        if not body:
            card_errors.append('Body is empty.')

        if card_errors:
            for message in card_errors:
                errors.append(ImportError_(index=i, title=title, message=message))
        else:
            cards.append(ParsedCard(
                index=i,
                title=title,
                teaser=teaser,
                body=body,
                takeaways_raw=takeaways_raw,
            ))

    return cards, errors


def _sanitize_marker_text(text):
    """Marker lines are matched without DOTALL and non-greedily up to '-->',
    so a title/teaser containing a newline or a literal '-->' would corrupt
    the marker on export. Neutralize both so export -> re-import round-trips."""
    return (text or '').replace('\n', ' ').replace('\r', ' ').replace('-->', '- >').strip()


def serialize_cards_to_markdown(cards):
    """
    Inverse of parse_markdown_cards: turn ProjectCard-like objects (needing
    only .title, .teaser, .body, .takeaways) back into the marker format,
    so an exported file can be edited and re-imported unchanged.
    """
    cards = list(cards)
    if not cards:
        return '<!-- No sections yet. Add cards in the admin, then export again. -->\n'

    blocks = []
    for card in cards:
        lines = [
            '<!-- CARD -->',
            f'<!-- TITLE: {_sanitize_marker_text(card.title)} -->',
            f'<!-- TEASER: {_sanitize_marker_text(card.teaser)} -->',
            (card.body or '').strip(),
        ]

        takeaways = [t.strip() for t in (card.takeaways or []) if t.strip()]
        if takeaways:
            lines.append('')
            lines.append('<!-- TAKEAWAYS -->')
            lines.extend(f'- {t}' for t in takeaways)

        lines.append('')
        lines.append('<!-- /CARD -->')
        blocks.append('\n'.join(lines))

    return '\n\n'.join(blocks) + '\n'
