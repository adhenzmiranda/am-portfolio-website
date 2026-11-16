"""Checks a submitted response against the survey it belongs to.

Nothing from the browser is trusted: every answer must be one the survey
offers, orders must be a shuffle of the prompt numbers, and scores are
computed on the server. Anything odd is rejected with SubmissionError (a 400).
"""
import math

from .logic import SEND_CODES
from .models import Question

MAX_SECONDS = 24 * 60 * 60


class SubmissionError(ValueError):
    pass


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def clean_answer(question, value):
    """Return the cleaned answer (None if unanswered) or raise SubmissionError."""
    if value is None or value == '' or value == []:
        if question.required:
            raise SubmissionError(f'{question.code}: required')
        return None
    kind = question.kind
    if kind in (Question.SHORT_TEXT, Question.LONG_TEXT):
        if not isinstance(value, str):
            raise SubmissionError(f'{question.code}: expected text')
        value = value.strip()
        limit = Question.SHORT_MAX if kind == Question.SHORT_TEXT else Question.LONG_MAX
        if len(value) > limit:
            raise SubmissionError(f'{question.code}: too long')
        if not value:
            if question.required:
                raise SubmissionError(f'{question.code}: required')
            return None
        return value
    if kind == Question.NUMBER:
        if not _is_int(value):
            raise SubmissionError(f'{question.code}: expected a whole number')
        if question.min_value is not None and value < question.min_value:
            raise SubmissionError(f'{question.code}: below minimum')
        if question.max_value is not None and value > question.max_value:
            raise SubmissionError(f'{question.code}: above maximum')
        return value
    if kind == Question.SCALE:
        if not _is_int(value) or not 1 <= value <= 5:
            raise SubmissionError(f'{question.code}: expected 1 to 5')
        return value
    if kind in (Question.CHOICE, Question.DROPDOWN):
        if value not in question.option_list():
            raise SubmissionError(f'{question.code}: not an option')
        return value
    if kind == Question.CHECKBOXES:
        options = question.option_list()
        if (not isinstance(value, list) or len(set(value)) != len(value)
                or any(v not in options for v in value)):
            raise SubmissionError(f'{question.code}: not a list of options')
        return [o for o in options if o in value]  # keep the survey's order
    raise SubmissionError(f'{question.code}: unknown question type')


def clean_task(order, answers, numbers, label):
    if (not isinstance(order, list) or not all(_is_int(n) for n in order)
            or sorted(order) != sorted(numbers)):
        raise SubmissionError(f'{label}_order: must be a shuffle of the prompt numbers')
    expected_keys = {str(n) for n in numbers}
    if not isinstance(answers, dict) or set(answers) != expected_keys:
        raise SubmissionError(f'{label}: answer every prompt')
    if any(v not in SEND_CODES for v in answers.values()):
        raise SubmissionError(f'{label}: not a valid choice')
    return list(order), {k: answers[k] for k in sorted(answers, key=int)}


def clean_seconds(value, name):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or math.isnan(value) \
            or not 0 <= value <= MAX_SECONDS:
        raise SubmissionError(f'timing.{name}: not a valid number of seconds')
    return round(float(value), 1)


def clean_submission(survey, condition, data):
    """data: the parsed JSON body. Returns a dict of Participant field values."""
    if not isinstance(data, dict):
        raise SubmissionError('body must be a JSON object')

    questions = survey.question_list()
    answers = data.get('answers')
    if not isinstance(answers, dict):
        raise SubmissionError('answers: missing')
    unknown = set(answers) - {q.code for q in questions}
    if unknown:
        raise SubmissionError(f'answers: unknown question {sorted(unknown)[0]}')
    cleaned_answers = {}
    for q in questions:
        value = clean_answer(q, answers.get(q.code))
        if value is not None:
            cleaned_answers[q.code] = value

    numbers = list(survey.prompts.values_list('number', flat=True))
    before_order, before = clean_task(data.get('before_order'), data.get('before'), numbers, 'before')
    after_order, after = clean_task(data.get('after_order'), data.get('after'), numbers, 'after')

    timing = data.get('timing') or {}
    if not isinstance(timing, dict):
        raise SubmissionError('timing: must be an object')
    is_video = condition.kind == condition.VIDEO
    finished = timing.get('video_finished')
    if finished is not None and not isinstance(finished, bool):
        raise SubmissionError('timing.video_finished: must be true or false')

    return {
        'answers': cleaned_answers,
        'before_order': before_order,
        'before_answers': before,
        'after_order': after_order,
        'after_answers': after,
        'message_seconds': clean_seconds(timing.get('message_seconds'), 'message_seconds'),
        'video_watched_seconds': clean_seconds(timing.get('video_watched_seconds'), 'video_watched_seconds') if is_video else None,
        'video_finished': finished if is_video else None,
        'total_seconds': clean_seconds(timing.get('total_seconds'), 'total_seconds'),
    }


def clean_source(value):
    """Recruitment tag from ?src=: letters, numbers, - and _ only, up to 60 characters."""
    if not isinstance(value, str):
        return ''
    value = value.strip().lower()[:60]
    return value if value and all(c.isalnum() or c in '-_' for c in value) and value.isascii() else ''
