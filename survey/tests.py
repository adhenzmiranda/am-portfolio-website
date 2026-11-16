import json
import os
from datetime import timedelta
from unittest import mock

# The test runner turns DEBUG off, and projects/urls.py then requires ADMIN_URL.
os.environ.setdefault('ADMIN_URL', 'admin-test')

from django.core.cache import cache  # noqa: E402
from django.core.exceptions import ValidationError  # noqa: E402
from django.test import TestCase, override_settings  # noqa: E402
from django.urls import reverse  # noqa: E402
from django.utils import timezone  # noqa: E402

from .admin import duplicate_survey  # noqa: E402
from .export import SurveyExport  # noqa: E402
from .logic import CHANGE, DONT_SEND, SEND, pick_condition, score  # noqa: E402
from .models import Condition, Participant, Question, Section, Survey  # noqa: E402
from .validation import clean_source  # noqa: E402


@override_settings(SECURE_SSL_REDIRECT=False)
class SurveyTestCase(TestCase):
    """Uses the seeded "Think Before You Prompt" survey (migration 0002)."""

    def setUp(self):
        cache.clear()   # rate-limit counters
        self.survey = Survey.objects.get(slug='msc-survey')
        # Make every media group usable without touching Cloudinary.
        for c in self.survey.conditions.all():
            c.kind, c.text_body = Condition.TEXT, f'{c.name} body'
            c.save()
        self.survey.researcher_email = 'researcher@example.com'
        self.survey.ethics_contact = 'supervisor@example.com'
        self.survey.ethics_reference = 'ETH-TEST-1'
        self.survey.status = Survey.OPEN
        self.survey.full_clean()
        self.survey.save()

    def url(self, name):
        return reverse(f'survey:{name}', args=[self.survey.slug])

    def post_json(self, name, body):
        return self.client.post(self.url(name), json.dumps(body), content_type='application/json')

    def start(self):
        res = self.post_json('start', {'source': 'rak-poster'})
        self.assertEqual(res.status_code, 200)
        return res.json()

    def valid_payload(self, token, **changes):
        questions = self.survey.question_list()
        answers = {'age': 21, 'gender': 'Female', 'university': 'Bath Spa RAK', 'emirate': 'Ras Al Khaimah',
                   'field_of_study': 'Business', 'chatbot_use': 'Daily', 'content_loaded': 'Yes'}
        answers.update({q.code: 4 for q in questions if q.kind == Question.SCALE})
        prompts = list(self.survey.prompts.all())
        payload = {
            'token': token,
            'answers': answers,
            'before_order': [1, 2, 3, 4, 5, 6, 7, 8],
            'before': {str(p.number): SEND for p in prompts},                          # 4 of 8
            'after_order': [8, 7, 6, 5, 4, 3, 2, 1],
            'after': {str(p.number): CHANGE if p.risky else SEND for p in prompts},    # 8 of 8
            'timing': {'message_seconds': 42.5, 'total_seconds': 600},
        }
        payload.update(changes)
        return payload


class PageTests(SurveyTestCase):
    def test_open_page_loads_without_answer_key(self):
        res = self.client.get(self.url('page'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['X-Robots-Tag'], 'noindex, nofollow')
        self.assertIn('no-store', res['Cache-Control'])
        config = res.context['config']
        self.assertEqual(config['mode'], 'live')
        self.assertTrue(all('risky' not in p for p in config['prompts']))
        self.assertNotContains(res, '"risky"')
        # Formatted text arrives as sanitised HTML in <template> tags, never inside the JSON.
        self.assertNotIn('html', config['consent'])
        self.assertContains(res, '<template id="rich-consent"><p>A short survey')
        self.assertContains(res, '<h3>About this study</h3>')

    def test_markdown_is_sanitised(self):
        self.survey.intro_text = 'Hi <script>alert(1)</script> <img src=x onerror=alert(2)>'
        self.survey.save()
        res = self.client.get(self.url('page'))
        self.assertNotContains(res, '<script>alert(1)')
        self.assertNotContains(res, 'onerror')

    def test_draft_is_404_for_the_public(self):
        Survey.objects.filter(pk=self.survey.pk).update(status=Survey.DRAFT)
        self.assertEqual(self.client.get(self.url('page')).status_code, 404)

    def test_closed_shows_the_closed_page(self):
        Survey.objects.filter(pk=self.survey.pk).update(status=Survey.CLOSED)
        res = self.client.get(self.url('page'))
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, 'survey/closed.html')
        self.assertContains(res, self.survey.closed_heading)

    def test_preview_works_on_a_draft_and_includes_the_answer_key(self):
        Survey.objects.filter(pk=self.survey.pk).update(status=Survey.DRAFT)
        with mock.patch('survey.views.can_preview', return_value=True):
            res = self.client.get(self.url('page') + '?preview=1')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['config']['mode'], 'preview')
        self.assertIn('risky', res.context['config']['prompts'][0])

    def test_review_link_opens_a_draft_without_login(self):
        from .views import review_key
        Survey.objects.filter(pk=self.survey.pk).update(status=Survey.DRAFT)
        res = self.client.get(self.url('page') + '?review=' + review_key(self.survey))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['config']['mode'], 'preview')   # nothing is saved in preview
        self.assertEqual(res['X-Robots-Tag'], 'noindex, nofollow')

    def test_wrong_review_key_gets_nothing(self):
        Survey.objects.filter(pk=self.survey.pk).update(status=Survey.DRAFT)
        self.assertEqual(self.client.get(self.url('page') + '?review=0123456789abcdef01234567').status_code, 404)
        self.assertEqual(self.client.get(self.url('page') + '?review=').status_code, 404)

    def test_review_link_changes_with_a_new_version(self):
        from .views import review_key
        before = review_key(self.survey)
        self.survey.version += 1
        self.assertNotEqual(review_key(self.survey), before)

    def test_preview_flag_ignored_for_the_public(self):
        res = self.client.get(self.url('page') + '?preview=1')
        self.assertEqual(res.context['config']['mode'], 'live')

    def test_unknown_address_is_404(self):
        self.assertEqual(self.client.get('/no-such-survey/').status_code, 404)

    def test_existing_pages_still_win(self):
        self.assertEqual(self.client.get(reverse('about')).resolver_match.url_name, 'about')


class StartTests(SurveyTestCase):
    def test_start_creates_a_row(self):
        data = self.start()
        p = Participant.objects.get(token=data['token'])
        self.assertEqual(p.condition.key, data['condition'])
        self.assertEqual(p.source, 'rak-poster')
        self.assertEqual(p.batch, self.survey.batch)
        self.assertIsNone(p.completed_at)

    def test_start_refused_when_not_open(self):
        for status in (Survey.DRAFT, Survey.CLOSED):
            Survey.objects.filter(pk=self.survey.pk).update(status=status)
            self.assertEqual(self.post_json('start', {}).status_code, 410)
        self.assertFalse(Participant.objects.exists())

    def test_start_needs_post(self):
        self.assertEqual(self.client.get(self.url('start')).status_code, 405)

    def test_balancing_picks_the_smallest_group(self):
        groups = {c.key: c for c in self.survey.conditions.all()}
        done = timezone.now()
        for key, n in (('video', 2), ('infographic', 2), ('text', 1)):
            for _ in range(n):
                Participant.objects.create(survey=self.survey, survey_version=1, batch=self.survey.batch,
                                           condition=groups[key], completed_at=done)
        self.assertEqual(self.start()['condition'], 'text')

    def test_old_drop_outs_do_not_hold_a_place(self):
        groups = {c.key: c for c in self.survey.conditions.all()}
        long_ago = timezone.now() - timedelta(hours=3)
        for key in ('video', 'video', 'infographic'):
            Participant.objects.create(survey=self.survey, survey_version=1, batch=self.survey.batch,
                                       condition=groups[key], started_at=long_ago)
        Participant.objects.create(survey=self.survey, survey_version=1, batch=self.survey.batch,
                                   condition=groups['text'], started_at=timezone.now())
        self.assertIn(pick_condition(self.survey, self.survey.batch).key, {'video', 'infographic'})

    def test_balancing_is_per_batch(self):
        groups = {c.key: c for c in self.survey.conditions.all()}
        for _ in range(3):
            Participant.objects.create(survey=self.survey, survey_version=1, batch='pilot-old',
                                       condition=groups['text'], completed_at=timezone.now())
        Participant.objects.create(survey=self.survey, survey_version=1, batch=self.survey.batch,
                                   condition=groups['video'], completed_at=timezone.now())
        Participant.objects.create(survey=self.survey, survey_version=1, batch=self.survey.batch,
                                   condition=groups['infographic'], completed_at=timezone.now())
        self.assertEqual(pick_condition(self.survey, self.survey.batch).key, 'text')


class SubmitTests(SurveyTestCase):
    def test_valid_submit_is_saved_with_server_scores(self):
        token = self.start()['token']
        payload = self.valid_payload(token)
        payload['before_score'] = 8   # anything the browser claims is ignored
        res = self.post_json('submit', payload)
        self.assertEqual(res.status_code, 200, res.content)
        p = Participant.objects.get(token=token)
        self.assertIsNotNone(p.completed_at)
        self.assertEqual((p.before_score, p.after_score, p.score_change), (4, 8, 4))
        self.assertEqual(p.answers['age'], 21)
        self.assertEqual(p.answers['university'], 'Bath Spa RAK')
        self.assertEqual(p.before_order, [1, 2, 3, 4, 5, 6, 7, 8])
        self.assertEqual(p.message_seconds, 42.5)
        self.assertIsNone(p.video_watched_seconds)   # not the video group

    def test_second_submit_is_refused(self):
        token = self.start()['token']
        self.assertEqual(self.post_json('submit', self.valid_payload(token)).status_code, 200)
        self.assertEqual(self.post_json('submit', self.valid_payload(token)).status_code, 410)

    def test_old_token_is_refused(self):
        token = self.start()['token']
        Participant.objects.filter(token=token).update(started_at=timezone.now() - timedelta(hours=7))
        self.assertEqual(self.post_json('submit', self.valid_payload(token)).status_code, 410)

    def test_unknown_token_is_refused(self):
        self.start()
        payload = self.valid_payload('00000000-0000-0000-0000-000000000000')
        self.assertEqual(self.post_json('submit', payload).status_code, 410)

    def test_bad_values_are_rejected(self):
        token = self.start()['token']
        base = self.valid_payload(token)
        ratings = {k: v for k, v in base['answers'].items() if not k.startswith('rating_8')}
        bad = {
            'wrong choice': {'before': {**base['before'], '1': 'maybe'}},
            'age 17': {'answers': {**base['answers'], 'age': 17}},
            'age as text': {'answers': {**base['answers'], 'age': '21'}},
            '7 ratings': {'answers': ratings},
            'rating 6': {'answers': {**base['answers'], 'rating_1_engagement': 6}},
            'not an option': {'answers': {**base['answers'], 'emirate': 'Narnia'}},
            'unknown question': {'answers': {**base['answers'], 'name': 'Sam'}},
            'broken order': {'after_order': [1, 1, 2, 3, 4, 5, 6, 7]},
            'short order': {'before_order': [1, 2, 3]},
            'missing prompt': {'after': {k: v for k, v in base['after'].items() if k != '8'}},
            'negative time': {'timing': {'message_seconds': -1}},
        }
        for label, change in bad.items():
            with self.subTest(label):
                res = self.post_json('submit', {**base, **change})
                self.assertEqual(res.status_code, 400, label)
        self.assertIsNone(Participant.objects.get(token=token).completed_at)

    def test_optional_question_can_be_skipped(self):
        Question.objects.filter(section__survey=self.survey, code='university').update(required=False)
        token = self.start()['token']
        payload = self.valid_payload(token)
        del payload['answers']['university']
        self.assertEqual(self.post_json('submit', payload).status_code, 200)

    def test_submit_refused_when_closed(self):
        token = self.start()['token']
        Survey.objects.filter(pk=self.survey.pk).update(status=Survey.CLOSED)
        self.assertEqual(self.post_json('submit', self.valid_payload(token)).status_code, 410)

    def test_nothing_identifying_is_stored(self):
        token = self.start()['token']
        self.post_json('submit', self.valid_payload(token), )
        fields = {f.name for f in Participant._meta.get_fields()}
        for forbidden in ('ip', 'ip_address', 'user_agent', 'email', 'name', 'student_id'):
            self.assertNotIn(forbidden, fields)


class ScoringTests(SurveyTestCase):
    def test_refusing_everything_scores_half(self):
        prompts = list(self.survey.prompts.all())
        self.assertEqual(score(prompts, {str(p.number): DONT_SEND for p in prompts}), 4)

    def test_perfect_answers_score_eight(self):
        prompts = list(self.survey.prompts.all())
        answers = {str(p.number): (DONT_SEND if p.risky else SEND) for p in prompts}
        self.assertEqual(score(prompts, answers), 8)


class BuilderRuleTests(SurveyTestCase):
    def test_cannot_open_without_contacts_and_ethics_reference(self):
        self.survey.researcher_email = ''
        self.survey.ethics_reference = ''
        with self.assertRaises(ValidationError):
            self.survey.full_clean()

    def test_page_order_is_enforced(self):
        media = self.survey.sections.get(kind=Section.MEDIA)
        media.order = 0
        media.save()
        self.assertTrue(any('order' in p for p in self.survey.structure_problems()))

    def test_duplicate_question_codes_are_flagged(self):
        Question.objects.filter(section__survey=self.survey, code='gender').update(code='age')
        self.assertTrue(any('"age"' in p for p in self.survey.structure_problems()))

    def test_media_group_without_media_is_flagged(self):
        c = self.survey.conditions.first()
        c.text_body = ''
        c.save()
        self.assertTrue(any(c.name in p for p in self.survey.structure_problems()))

    def test_locked_once_answered(self):
        self.assertFalse(self.survey.is_locked)
        self.start()
        self.assertTrue(self.survey.is_locked)

    def test_reserved_address(self):
        self.survey.slug = 'projects'
        with self.assertRaises(ValidationError):
            self.survey.full_clean()

    def test_duplicate_makes_an_editable_next_version(self):
        self.start()
        copy = duplicate_survey(self.survey)
        self.assertEqual(copy.status, Survey.DRAFT)
        self.assertEqual(copy.version, self.survey.version + 1)
        self.assertNotEqual(copy.slug, self.survey.slug)
        self.assertFalse(copy.is_locked)
        self.assertEqual(copy.sections.count(), self.survey.sections.count())
        self.assertEqual(len(copy.question_list()), len(self.survey.question_list()))
        self.assertEqual(copy.prompts.count(), 8)
        self.assertEqual(copy.conditions.count(), 3)
        self.assertEqual(self.survey.sections.count(), 6)   # original untouched

    def test_source_tags(self):
        self.assertEqual(clean_source('RAK-Poster'), 'rak-poster')
        self.assertEqual(clean_source('<script>'), '')
        self.assertEqual(clean_source(None), '')


class ExportTests(SurveyTestCase):
    def test_header_and_rows_line_up(self):
        token = self.start()['token']
        self.post_json('submit', self.valid_payload(token))
        self.start()   # a drop-out
        export = SurveyExport(self.survey)
        header = export.header()
        for p in self.survey.participants.select_related('condition'):
            self.assertEqual(len(export.row(p)), len(header))
        self.assertIn('before_p1_correct', header)
        self.assertIn('mean_engagement', header)
        self.assertIn('rating_8_intention', header)

    def test_values_and_formula_injection(self):
        token = self.start()['token']
        payload = self.valid_payload(token)
        payload['answers']['university'] = '=HYPERLINK("http://evil")'
        self.post_json('submit', payload)
        export = SurveyExport(self.survey)
        p = Participant.objects.get(token=token)
        row = dict(zip(export.header(), export.row(p)))
        self.assertEqual(row['university'], '\'=HYPERLINK("http://evil")')
        self.assertEqual(row['before_score'], 4)
        self.assertEqual(row['before_p1'], 'send')
        self.assertEqual(row['before_p1_correct'], 0)   # prompt 1 is risky
        self.assertEqual(row['after_p1_correct'], 1)
        self.assertEqual(row['mean_engagement'], 4.0)
        self.assertEqual(row['completed'], 1)

    def test_attention_check_column(self):
        q = Question.objects.get(section__survey=self.survey, code='chatbot_use')
        q.attention_answer = 'Weekly'
        q.save()
        token = self.start()['token']
        self.post_json('submit', self.valid_payload(token))   # answered "Daily"
        export = SurveyExport(self.survey)
        row = dict(zip(export.header(), export.row(Participant.objects.get(token=token))))
        self.assertEqual(row['chatbot_use_passed'], 0)
