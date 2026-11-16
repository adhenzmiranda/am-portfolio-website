"""CSV export: one row per person, columns in the order the participant went through the survey.

    1. The response    response_id, completed, started_uae, completed_uae, total_minutes
    2. Setup           batch, source, media_group, survey_version
    3. The pages, in survey order, each as its own block:
         questions page    one column per question (by its code) + <code>_passed for attention checks
         "before" task     before_score, before_p1..p8 (send / change / dont_send),
                           before_p1_correct..p8_correct (1/0), before_order
         media page        media_seconds, video_watched_seconds, video_finished
         "after" task      after_score, score_change, after_p1..p8, after_p1_correct..p8_correct, after_order
    4. Construct means mean_<construct> for each group of rating statements
    5. Technical       started_utc, completed_utc, token

Times are UAE local time (Asia/Dubai, UTC+4) as "YYYY-MM-DD HH:MM:SS", which Excel and
Google Sheets read as dates. The exact UTC timestamps are kept at the end.
"""
import csv
import io
from zoneinfo import ZoneInfo

from .logic import CONSTRUCT_ORDER, attention_passed, construct_means, is_correct
from .models import Section

UAE = ZoneInfo('Asia/Dubai')

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


def _uae(dt):
    return dt.astimezone(UAE).strftime('%Y-%m-%d %H:%M:%S') if dt else ''


class SurveyExport:
    def __init__(self, survey):
        self.survey = survey
        self.sections = list(survey.sections.prefetch_related('questions'))
        self.questions = survey.question_list()
        self.prompts = list(survey.prompts.all())
        used = {q.construct for q in self.questions if q.construct}
        self.constructs = [c for c in CONSTRUCT_ORDER if c in used] + sorted(used - set(CONSTRUCT_ORDER))
        self.blocks = self._blocks()

    # ---- one block per kind of page

    def _task_cols(self, phase):
        cols = [f'{phase}_score'] + (['score_change'] if phase == 'after' else [])
        cols += [f'{phase}_p{p.number}' for p in self.prompts]
        cols += [f'{phase}_p{p.number}_correct' for p in self.prompts]
        return cols + [f'{phase}_order']

    def _task_vals(self, p, phase):
        answers = p.before_answers if phase == 'before' else p.after_answers
        vals = [_cell(p.before_score if phase == 'before' else p.after_score)]
        if phase == 'after':
            vals.append(_cell(p.score_change))
        vals += [answers.get(str(pr.number), '') for pr in self.prompts]
        vals += [_flag(is_correct(pr.risky, answers[str(pr.number)])) if str(pr.number) in answers else ''
                 for pr in self.prompts]
        order = p.before_order if phase == 'before' else p.after_order
        return vals + [' '.join(map(str, order))]

    def _blocks(self):
        """[(columns, function(participant) -> values)] in survey order."""
        blocks = []
        for section in self.sections:
            if section.kind == Section.QUESTIONS:
                for q in section.questions.all():
                    cols = [q.code] + ([f'{q.code}_passed'] if q.attention_answer.strip() else [])
                    blocks.append((cols, lambda p, q=q: (
                        [_safe(_cell(p.answers.get(q.code)))]
                        + ([_flag(attention_passed(q, p.answers.get(q.code)))] if q.attention_answer.strip() else []))))
            elif section.kind == Section.TASK_BEFORE:
                blocks.append((self._task_cols('before'), lambda p: self._task_vals(p, 'before')))
            elif section.kind == Section.MEDIA:
                blocks.append((['media_seconds', 'video_watched_seconds', 'video_finished'], lambda p: [
                    _cell(p.message_seconds), _cell(p.video_watched_seconds), _flag(p.video_finished)]))
            elif section.kind == Section.TASK_AFTER:
                blocks.append((self._task_cols('after'), lambda p: self._task_vals(p, 'after')))
        return blocks

    # ---- the table

    def header(self):
        cols = ['response_id', 'completed', 'started_uae', 'completed_uae', 'total_minutes',
                'batch', 'source', 'media_group', 'survey_version']
        for block_cols, _ in self.blocks:
            cols += block_cols
        cols += [f'mean_{c}' for c in self.constructs]
        return cols + ['started_utc', 'completed_utc', 'token']

    def row(self, p):
        done = p.completed
        minutes = round(p.total_seconds / 60, 1) if p.total_seconds is not None else ''
        out = [p.pk, int(done), _uae(p.started_at), _uae(p.completed_at), minutes,
               p.batch, p.source, p.condition.key, p.survey_version]
        for _, values in self.blocks:
            out += values(p)
        means = construct_means(self.questions, p.answers)
        out += [means.get(c, '') for c in self.constructs]
        return out + [p.started_at.isoformat(), p.completed_at.isoformat() if done else '', str(p.token)]

    def to_csv(self, participants):
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(self.header())
        for p in participants:
            writer.writerow(self.row(p))
        # BOM so Excel opens accented and Arabic text correctly; Python and Sheets ignore it.
        return '﻿' + buffer.getvalue()
