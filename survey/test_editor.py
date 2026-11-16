import json
import os
from unittest import mock

os.environ.setdefault('ADMIN_URL', 'admin-test')

from django.core.cache import cache  # noqa: E402
from django.test import TestCase, override_settings  # noqa: E402
from django.utils import timezone  # noqa: E402

from .models import Condition, Participant, Prompt, Question, Section, Survey  # noqa: E402


@override_settings(SECURE_SSL_REDIRECT=False)
class EditorTestCase(TestCase):
    """The editor API, logged in (can_preview patched) unless a test says otherwise."""

    def setUp(self):
        cache.clear()
        self.survey = Survey.objects.get(slug='msc-survey')
        patcher = mock.patch('survey.editor.can_preview', return_value=True)
        self.allowed = patcher.start()
        self.addCleanup(patcher.stop)

    def api(self, path, body=None):
        return self.client.post(f'/{self.survey.slug}/edit/api/{path}', json.dumps(body or {}),
                                content_type='application/json')

    def question(self, code):
        return Question.objects.get(section__survey=self.survey, code=code)

    def lock(self):
        Participant.objects.create(survey=self.survey, survey_version=1, batch='pilot',
                                   condition=self.survey.conditions.first())


class AccessTests(EditorTestCase):
    def test_page_redirects_to_admin_login_when_not_logged_in(self):
        self.allowed.return_value = False
        res = self.client.get('/msc-survey/edit/')
        self.assertEqual(res.status_code, 302)
        self.assertIn('/login/?next=/msc-survey/edit/', res['Location'])

    def test_api_refuses_when_not_logged_in(self):
        self.allowed.return_value = False
        self.assertEqual(self.api(f'question/{self.question("age").pk}/', {'text': 'x'}).status_code, 403)
        self.assertEqual(self.client.get('/msc-survey/edit/api/state/').status_code, 403)
        self.assertEqual(self.question('age').text, 'Age')

    def test_page_loads_for_the_researcher(self):
        res = self.client.get('/msc-survey/edit/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['X-Robots-Tag'], 'noindex, nofollow')
        self.assertIn('csrftoken', res.cookies)          # the API calls send it back
        self.assertNotContains(res, 'application/json')  # a shell: the data comes from the API
        state = self.client.get('/msc-survey/edit/api/state/').json()
        self.assertEqual(len(state['sections']), 6)
        self.assertEqual(len(state['prompts']), 8)
        self.assertTrue(state['problems'])
        self.assertIn('questionKinds', state['choices'])

    def test_survey_pages_cannot_be_framed(self):
        with mock.patch('survey.views.can_preview', return_value=True):
            res = self.client.get('/msc-survey/?preview=1')
        self.assertEqual(res['X-Frame-Options'], 'DENY')


class UpdateTests(EditorTestCase):
    def test_edit_a_question(self):
        q = self.question('gender')
        res = self.api(f'question/{q.pk}/', {'text': 'What is your gender?', 'options': 'Male\nFemale\nOther'})
        self.assertEqual(res.status_code, 200, res.content)
        q.refresh_from_db()
        self.assertEqual(q.text, 'What is your gender?')
        self.assertEqual(q.option_list(), ['Male', 'Female', 'Other'])
        self.assertEqual(res.json()['item']['text'], 'What is your gender?')

    def test_bad_values_are_refused(self):
        q = self.question('gender')
        self.assertEqual(self.api(f'question/{q.pk}/', {'kind': 'telepathy'}).status_code, 400)
        res = self.api(f'question/{q.pk}/', {'code': 'age'})
        self.assertEqual(res.status_code, 400)
        self.assertIn('code', res.json()['errors'])
        self.assertEqual(self.api(f'question/{q.pk}/', {'survey': 3}).status_code, 400)   # not an editable field
        self.assertEqual(self.api('survey/0/', {'slug': 'projects'}).status_code, 400)       # reserved address

    def test_prompt_numbers_stay_unique(self):
        p = Prompt.objects.get(survey=self.survey, number=2)
        res = self.api(f'prompt/{p.pk}/', {'number': 1})
        self.assertEqual(res.status_code, 400)
        self.assertIn('number', res.json()['errors'])
        self.assertEqual(self.api(f'prompt/{p.pk}/', {'risky': True}).status_code, 200)

    def test_cannot_open_until_ready(self):
        res = self.api('survey/0/', {'status': Survey.OPEN})
        self.assertEqual(res.status_code, 400)
        self.assertIn('status', res.json()['errors'])
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.status, Survey.DRAFT)

    def test_items_from_another_survey_are_404(self):
        from .admin import duplicate_survey
        other = duplicate_survey(self.survey)
        q = Question.objects.filter(section__survey=other).first()
        self.assertEqual(self.api(f'question/{q.pk}/', {'text': 'x'}).status_code, 404)

    def test_changing_the_address_redirects_the_editor(self):
        res = self.api('survey/0/', {'slug': 'msc'})
        self.assertEqual(res.json()['redirect'], '/msc/edit/')


class LockTests(EditorTestCase):
    def test_locked_survey_refuses_content_changes(self):
        self.lock()
        q = self.question('gender')
        self.assertEqual(self.api(f'question/{q.pk}/', {'text': 'Changed'}).status_code, 403)
        self.assertEqual(self.api('survey/0/', {'intro_text': 'Changed'}).status_code, 403)
        self.assertEqual(self.api('question/new/', {'section': q.section_id}).status_code, 403)
        self.assertEqual(self.api(f'question/{q.pk}/delete/').status_code, 403)
        self.assertEqual(self.api('reorder/', {'kind': 'section', 'ids': []}).status_code, 403)
        self.assertEqual(self.question('gender').text, 'Gender')

    def test_locked_survey_still_allows_settings(self):
        self.lock()
        res = self.api('survey/0/', {'batch': 'main', 'closed_message': 'Done, thanks!',
                                     'researcher_email': 'me@example.com'})
        self.assertEqual(res.status_code, 200, res.content)
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.batch, 'main')


class StructureTests(EditorTestCase):
    def test_add_and_delete_a_question(self):
        section = self.survey.sections.get(title='About you')
        res = self.api('question/new/', {'section': section.pk, 'kind': 'checkboxes'})
        self.assertEqual(res.status_code, 200)
        item = res.json()['item']
        self.assertEqual(item['kind'], 'checkboxes')
        self.assertEqual(item['code'], 'question')
        self.assertEqual(item['options'], 'Option 1')
        self.assertEqual(self.api(f'question/{item["id"]}/delete/').status_code, 200)
        self.assertFalse(Question.objects.filter(pk=item['id']).exists())

    def test_questions_only_go_on_questions_pages(self):
        media = self.survey.sections.get(kind=Section.MEDIA)
        self.assertEqual(self.api('question/new/', {'section': media.pk}).status_code, 400)

    def test_add_page_prompt_and_media_group(self):
        self.assertEqual(self.api('section/new/', {'kind': 'info'}).json()['item']['title'], 'Untitled page')
        self.assertEqual(self.api('prompt/new/').json()['item']['number'], 9)
        group = self.api('condition/new/', {'kind': 'video'}).json()['item']
        self.assertEqual((group['key'], group['kind']), ('group', 'video'))
        self.assertEqual(self.api('section/new/', {'kind': 'nonsense'}).status_code, 400)

    def test_duplicate_question_goes_right_after_the_original(self):
        q = self.question('gender')
        copy = self.api(f'question/{q.pk}/duplicate/').json()['item']
        self.assertEqual(copy['code'], 'gender_copy')
        codes = list(q.section.questions.values_list('code', flat=True))
        self.assertEqual(codes[codes.index('gender') + 1], 'gender_copy')

    def test_reorder_pages(self):
        ids = list(self.survey.sections.values_list('pk', flat=True))
        res = self.api('reorder/', {'kind': 'section', 'ids': list(reversed(ids))})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(list(self.survey.sections.values_list('pk', flat=True)), list(reversed(ids)))
        self.assertTrue(any('order' in p for p in res.json()['problems']))   # the checklist notices
        self.assertEqual(self.api('reorder/', {'kind': 'section', 'ids': ids[:2]}).status_code, 400)

    def test_move_a_question_to_another_page(self):
        q = self.question('content_loaded')
        about = self.survey.sections.get(title='About you')
        ids = list(about.questions.values_list('pk', flat=True)) + [q.pk]
        self.assertEqual(self.api('reorder/', {'kind': 'question', 'section': about.pk, 'ids': ids}).status_code, 200)
        q.refresh_from_db()
        self.assertEqual(q.section_id, about.pk)
        self.assertEqual(list(about.questions.values_list('pk', flat=True))[-1], q.pk)

    def test_upload_rejects_non_images(self):
        p = Prompt.objects.get(survey=self.survey, number=1)
        from django.core.files.uploadedfile import SimpleUploadedFile
        res = self.client.post(f'/msc-survey/edit/api/prompt/{p.pk}/upload/screenshot/',
                               {'file': SimpleUploadedFile('notes.txt', b'hello', content_type='text/plain')})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(self.client.post(f'/msc-survey/edit/api/prompt/{p.pk}/upload/text/').status_code, 404)

    def test_forged_video_reference_is_refused(self):
        c = Condition.objects.get(survey=self.survey, key='video')
        res = self.api(f'condition/{c.pk}/', {'video': 'video/upload/v1/survey/evil.mp4#notasignature'})
        self.assertEqual(res.status_code, 400)
        c.refresh_from_db()
        self.assertFalse(c.video)

    def test_duplicate_survey(self):
        res = self.api('duplicate-survey/')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(Survey.objects.filter(slug='msc-survey-v2').exists())
        self.assertEqual(res.json()['redirect'], '/msc-survey-v2/edit/')

    def test_state_endpoint(self):
        Participant.objects.create(survey=self.survey, survey_version=1, batch=self.survey.batch,
                                   condition=self.survey.conditions.first(), completed_at=timezone.now())
        data = self.client.get('/msc-survey/edit/api/state/').json()
        self.assertTrue(data['locked'])
        self.assertEqual(data['progress']['completed'], 1)
