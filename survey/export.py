"""CSV export: one row per person, columns built from the survey itself.

Columns: ids and dates, every question (by its code), attention-check
results, each prompt's before/after answer and whether it was correct, the
scores, a mean per construct, timing, and the two orders as shown.
Choice answers use the codes send / change / dont_send.
"""
import csv
import io

from .logic import attention_passed, construct_means, is_correct

# Cells starting with these would run as formulas in Excel / Google Sheets.
FORMULA_PREFIXES = ('=', '+', '-', '@', '\t', '\r')


def _safe(value):
    if isinstance(value, str) and value.startswith(FORMULA_PREFIXES):
        return "'" + value
    return value


def _flag(value):
    return '' if value is None else int(bool(value))


def _cell(value):
    if value is None:
        return ''
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, list):
        return '; '.join(str(v) for v in value)
    return value


class SurveyExport:
    def __init__(self, survey):
        self.survey = survey
        self.questions = survey.question_list()
        self.prompts = list(survey.prompts.all())
        self.constructs = sorted({q.construct for q in self.questions if q.construct})

    def header(self):
        cols = ['participant_id', 'token', 'survey', 'survey_version', 'batch', 'source', 'condition',
                'started_at', 'completed_at', 'completed']
        for q in self.questions:
            cols.append(q.code)
            if q.attention_answer.strip():
                cols.append(f'{q.code}_passed')
        for phase in ('before', 'after'):
            cols += [f'{phase}_p{p.number}' for p in self.prompts]
            cols += [f'{phase}_p{p.number}_correct' for p in self.prompts]
        cols += ['before_score', 'after_score', 'score_change']
        cols += [f'mean_{c}' for c in self.constructs]
        cols += ['message_seconds', 'video_watched_seconds', 'video_finished', 'total_seconds',
                 'before_order', 'after_order']
        return cols

    def row(self, p):
        done = p.completed
        out = [p.pk, str(p.token), self.survey.slug, p.survey_version, p.batch, p.source, p.condition.key,
               p.started_at.isoformat(), p.completed_at.isoformat() if done else '', int(done)]
        for q in self.questions:
            value = p.answers.get(q.code)
            out.append(_safe(_cell(value)))
            if q.attention_answer.strip():
                out.append(_flag(attention_passed(q, value)))
        for phase, answers in (('before', p.before_answers), ('after', p.after_answers)):
            out += [answers.get(str(pr.number), '') for pr in self.prompts]
            out += [_flag(is_correct(pr.risky, answers[str(pr.number)])) if str(pr.number) in answers else ''
                    for pr in self.prompts]
        out += [_cell(p.before_score), _cell(p.after_score), _cell(p.score_change)]
        means = construct_means(self.questions, p.answers)
        out += [means.get(c, '') for c in self.constructs]
        out += [_cell(p.message_seconds), _cell(p.video_watched_seconds), _flag(p.video_finished),
                _cell(p.total_seconds), ' '.join(map(str, p.before_order)), ' '.join(map(str, p.after_order))]
        return out

    def to_csv(self, participants):
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(self.header())
        for p in participants:
            writer.writerow(self.row(p))
        # BOM so Excel opens accented and Arabic text correctly; Python and Sheets ignore it.
        return '﻿' + buffer.getvalue()
