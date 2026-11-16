"""Scoring and group assignment. Pure functions where possible, so they are easy to test."""
import random
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

# "Would you send this?" choices: (code saved and exported, label shown).
SEND, CHANGE, DONT_SEND = 'send', 'change', 'dont_send'
SEND_CHOICES = [(SEND, 'Send as is'), (CHANGE, 'Change it first'), (DONT_SEND, 'Wouldn’t send')]
SEND_CODES = [code for code, _ in SEND_CHOICES]

# People who started this long ago without finishing count as dropped out
# (no longer hold a place when balancing groups).
RECENT_START = timedelta(minutes=60)
# A token can be submitted for this long after starting.
TOKEN_LIFETIME = timedelta(hours=6)

_rng = random.SystemRandom()


def is_correct(risky, answer):
    """Risky: "Change it first" or "Wouldn't send" is correct.
    Safe: "Send as is" is correct (stops "refuse everything" scoring full marks)."""
    if risky:
        return answer in (CHANGE, DONT_SEND)
    return answer == SEND


def score(prompts, answers):
    """prompts: iterable of objects with .number and .risky; answers: {"1": code, ...}."""
    return sum(1 for p in prompts if is_correct(p.risky, answers.get(str(p.number))))


def pick_condition(survey, batch, now=None):
    """Balanced random assignment ("Evenly Present Elements").

    Picks the active group with the fewest people in this batch, counting
    finished people plus anyone who started in the last 60 minutes, and
    breaks ties at random. Methods wording: "Participants were randomly
    assigned to one of N conditions using balanced allocation."
    """
    now = now or timezone.now()
    conditions = list(survey.conditions.filter(active=True))
    if not conditions:
        return None
    counted = (survey.participants.filter(batch=batch)
               .filter(Q(completed_at__isnull=False) | Q(started_at__gte=now - RECENT_START))
               .values('condition').annotate(n=Count('id')))
    counts = {row['condition']: row['n'] for row in counted}
    fewest = min(counts.get(c.pk, 0) for c in conditions)
    return _rng.choice([c for c in conditions if counts.get(c.pk, 0) == fewest])


def construct_means(questions, answers):
    """{construct: mean} over answered scale questions that have a construct."""
    groups = {}
    for q in questions:
        value = answers.get(q.code)
        if q.construct and isinstance(value, int):
            groups.setdefault(q.construct, []).append(value)
    return {c: round(sum(v) / len(v), 2) for c, v in groups.items()}


def attention_passed(question, value):
    """True/False for an attention-check question, None for normal questions or no answer."""
    expected = question.attention_answer.strip()
    if not expected or value in (None, '', []):
        return None
    if isinstance(value, list):
        return [str(v).strip().lower() for v in value] == [expected.lower()]
    return str(value).strip().lower() == expected.lower()
