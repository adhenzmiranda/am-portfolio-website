import json
import os
import time
from unittest import mock
from urllib.parse import parse_qs, urlsplit

os.environ.setdefault('ADMIN_URL', 'admin-test')

from django.core.cache import cache  # noqa: E402
from django.core.files.uploadedfile import SimpleUploadedFile  # noqa: E402
from django.test import TestCase, override_settings  # noqa: E402

from projects.models import Category, ProjectCard, Projects  # noqa: E402

CHAPTERS_MD = """<!-- CARD -->
<!-- TITLE: The Dependency -->
<!-- TEASER: Healthcare runs on a network it does not control. -->
Body text for the first chapter.

<!-- TAKEAWAYS -->
- Point one
- Point two
<!-- /CARD -->

<!-- CARD -->
<!-- TITLE: The Fix -->
<!-- TEASER: What changes next. -->
Second chapter body.
<!-- /CARD -->
"""


@override_settings(SECURE_SSL_REDIRECT=False)
class StudioTestCase(TestCase):
    def setUp(self):
        cache.clear()
        patcher = mock.patch('studio.access.is_studio_user', return_value=True)
        self.allowed = patcher.start()
        self.addCleanup(patcher.stop)
        self.project = Projects.objects.create(name='Test project', description='Hello', year=2025)
        self.other = Projects.objects.create(name='Other project', description='Other', year=2024, display_mode='blogpost')

    def post(self, path, body=None):
        return self.client.post('/studio/api/' + path, json.dumps(body or {}), content_type='application/json')

    def get(self, path):
        return self.client.get('/studio/api/' + path)

    @property
    def base(self):
        return f'projects/{self.project.pk}/'


class AccessTests(StudioTestCase):
    def test_pages_redirect_to_the_admin_login(self):
        self.allowed.return_value = False
        for url in ('/studio/', '/studio/projects/', f'/studio/projects/{self.project.pk}/'):
            res = self.client.get(url)
            self.assertEqual(res.status_code, 302, url)
            self.assertIn('/login/?', res['Location'])
            self.assertEqual(parse_qs(urlsplit(res['Location']).query)['next'], [url])

    def test_login_redirect_keeps_the_whole_link(self):
        self.allowed.return_value = False
        res = self.client.get('/studio/projects/?mode=blogpost&featured=1')
        self.assertEqual(parse_qs(urlsplit(res['Location']).query)['next'], ['/studio/projects/?mode=blogpost&featured=1'])

    def test_api_refuses_without_login(self):
        self.allowed.return_value = False
        self.assertEqual(self.get('dashboard/').status_code, 403)
        self.assertEqual(self.post(self.base, {'name': 'Hacked'}).status_code, 403)
        self.assertEqual(Projects.objects.get(pk=self.project.pk).name, 'Test project')

    def test_pages_load_and_are_private(self):
        for url, script in (('/studio/', 'dashboard.js'), ('/studio/projects/', 'projects.js'),
                            (f'/studio/projects/{self.project.pk}/', 'project.js')):
            res = self.client.get(url)
            self.assertEqual(res.status_code, 200, url)
            self.assertEqual(res['X-Robots-Tag'], 'noindex, nofollow')
            self.assertIn('no-store', res['Cache-Control'])
            self.assertContains(res, 'studio/' + script)
            self.assertIn('csrftoken', res.cookies)

    def test_unknown_project_page_is_404(self):
        self.assertEqual(self.client.get('/studio/projects/99999/').status_code, 404)


class DashboardAndListTests(StudioTestCase):
    def test_dashboard_counts(self):
        Projects.objects.filter(pk=self.project.pk).update(featured=True)
        data = self.get('dashboard/').json()
        self.assertEqual(data['counts'], {'total': 2, 'featured': 1, 'blog': 1, 'portfolio': 1})
        self.assertEqual(len(data['recent']), 2)

    def test_project_list(self):
        data = self.get('projects/').json()
        self.assertEqual({p['name'] for p in data['projects']}, {'Test project', 'Other project'})
        self.assertEqual(data['projects'][0]['editor'], f'/studio/projects/{self.project.pk}/')


class ProjectTests(StudioTestCase):
    def test_create(self):
        res = self.post('projects/new/', {'name': 'Brand new', 'mode': 'blogpost'})
        self.assertEqual(res.status_code, 200, res.content)
        created = Projects.objects.get(name='Brand new')
        self.assertEqual(created.display_mode, 'blogpost')
        self.assertEqual(res.json()['project']['editor'], f'/studio/projects/{created.pk}/')

    def test_create_needs_a_unique_name(self):
        self.assertEqual(self.post('projects/new/', {'name': '  '}).status_code, 400)
        res = self.post('projects/new/', {'name': 'test PROJECT'})
        self.assertEqual(res.status_code, 400)
        self.assertIn('name', res.json()['errors'])

    def test_state(self):
        ProjectCard.objects.create(project=self.project, title='A', teaser='B', body='C')
        data = self.get(self.base).json()
        self.assertEqual(data['project']['name'], 'Test project')
        self.assertEqual(len(data['cards']), 1)
        self.assertIn('technologies', data['choices'])

    def test_edit_fields(self):
        cat = Category.objects.create(name='Games')
        res = self.post(self.base, {'name': 'Renamed', 'year': 2023, 'featured': True, 'category': cat.pk,
                                    'technologies': ['python', 'django'], 'description': '## Hi'})
        self.assertEqual(res.status_code, 200, res.content)
        p = Projects.objects.get(pk=self.project.pk)
        self.assertEqual((p.name, p.year, p.featured, p.category_id), ('Renamed', 2023, True, cat.pk))
        self.assertEqual(sorted(p.technologies), ['django', 'python'])

    def test_bad_values_are_refused(self):
        cases = {
            'year': {'year': 1800},
            'name': {'name': 'Other project'},
            'technologies': {'technologies': ['not-a-tech']},
            'display_mode': {'display_mode': 'magazine'},
            'description': {'description': ''},
        }
        for field, patch in cases.items():
            with self.subTest(field):
                res = self.post(self.base, patch)
                self.assertEqual(res.status_code, 400, field)
                self.assertIn(field, res.json()['errors'])
        self.assertEqual(self.post(self.base, {'id': 5}).status_code, 400)   # not an editable field

    def test_add_category_inline(self):
        res = self.post('categories/new/', {'name': 'Photography'})
        self.assertEqual(res.json()['category'][1], 'Photography')
        again = self.post('categories/new/', {'name': 'photography'})   # case-insensitive reuse
        self.assertEqual(again.json()['category'][0], res.json()['category'][0])

    def test_delete(self):
        res = self.post(self.base + 'delete/')
        self.assertEqual(res.json()['redirect'], '/studio/projects/')
        self.assertFalse(Projects.objects.filter(pk=self.project.pk).exists())

    def test_uploads_reject_bad_files(self):
        res = self.client.post(f'/studio/api/{self.base}upload/thumbnail_image/',
                               {'file': SimpleUploadedFile('notes.txt', b'hello', content_type='text/plain')})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(self.client.post(f'/studio/api/{self.base}upload/name/').status_code, 404)

    def test_upload_and_remove_images_without_touching_cloudinary(self):
        from cloudinary import CloudinaryResource
        fake = CloudinaryResource('studio-test/cover', format='png', type='upload', resource_type='image')
        png = SimpleUploadedFile('cover.png', b'\x89PNG\r\n\x1a\n' + b'0' * 64, content_type='image/png')
        with mock.patch('cloudinary.models.uploader.upload_resource', return_value=fake) as upload:
            res = self.client.post(f'/studio/api/{self.base}upload/thumbnail_image/', {'file': png})
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(upload.call_count, 1)
        self.assertEqual(Projects.objects.get(pk=self.project.pk).thumbnail_image.public_id, 'studio-test/cover')
        res = self.client.post(f'/studio/api/{self.base}upload/thumbnail_image/', {'clear': '1'})
        self.assertEqual(res.status_code, 200, res.content)
        self.assertFalse(Projects.objects.get(pk=self.project.pk).thumbnail_image)

        card = ProjectCard.objects.create(project=self.project, title='A', teaser='a', body='a')
        img = SimpleUploadedFile('chapter.png', b'\x89PNG\r\n\x1a\n', content_type='image/png')
        with mock.patch('cloudinary.models.uploader.upload_resource', return_value=fake):
            res = self.client.post(f'/studio/api/{self.base}cards/{card.pk}/upload/image/', {'file': img})
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(ProjectCard.objects.get(pk=card.pk).image.public_id, 'studio-test/cover')

    def test_failed_cloudinary_upload_is_reported(self):
        png = SimpleUploadedFile('cover.png', b'\x89PNG\r\n\x1a\n', content_type='image/png')
        with mock.patch('cloudinary.models.uploader.upload_resource', side_effect=RuntimeError('down')), \
                self.assertLogs('studio', level='ERROR'):
            res = self.client.post(f'/studio/api/{self.base}upload/thumbnail_image/', {'file': png})
        self.assertEqual(res.status_code, 502)
        self.assertFalse(Projects.objects.get(pk=self.project.pk).thumbnail_image)

    def test_preview_is_sanitised(self):
        res = self.post('preview/', {'markdown': '## Title\n\n<script>alert(1)</script> <img src=x onerror=alert(2)> **bold**'})
        html = res.json()['html']
        self.assertIn('<h2>Title</h2>', html)
        self.assertIn('<strong>bold</strong>', html)
        self.assertNotIn('<script', html)
        self.assertNotIn('onerror', html)


class ChapterTests(StudioTestCase):
    def test_add_edit_delete(self):
        item = self.post(self.base + 'cards/new/').json()['item']
        res = self.post(f'{self.base}cards/{item["id"]}/', {'title': 'Intro', 'takeaways_raw': 'One\nTwo'})
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(ProjectCard.objects.get(pk=item['id']).title, 'Intro')
        self.assertEqual(self.post(f'{self.base}cards/{item["id"]}/', {'title': ''}).status_code, 400)
        self.post(f'{self.base}cards/{item["id"]}/delete/')
        self.assertFalse(ProjectCard.objects.filter(pk=item['id']).exists())

    def test_cards_from_another_project_are_404(self):
        theirs = ProjectCard.objects.create(project=self.other, title='T', teaser='T', body='T')
        self.assertEqual(self.post(f'{self.base}cards/{theirs.pk}/', {'title': 'x'}).status_code, 404)
        self.assertEqual(self.post(f'{self.base}cards/{theirs.pk}/delete/').status_code, 404)

    def test_reorder(self):
        a = ProjectCard.objects.create(project=self.project, title='A', teaser='a', body='a', order=1)
        b = ProjectCard.objects.create(project=self.project, title='B', teaser='b', body='b', order=2)
        self.assertEqual(self.post(self.base + 'cards/reorder/', {'ids': [b.pk, a.pk]}).status_code, 200)
        self.assertEqual(list(self.project.cards.values_list('title', flat=True)), ['B', 'A'])
        self.assertEqual(self.post(self.base + 'cards/reorder/', {'ids': [b.pk]}).status_code, 400)

    def test_import_preview_then_commit(self):
        preview = self.post(self.base + 'cards/import/', {'markdown': CHAPTERS_MD}).json()
        self.assertEqual([c['title'] for c in preview['cards']], ['The Dependency', 'The Fix'])
        self.assertEqual(preview['errors'], [])
        self.assertEqual(self.project.cards.count(), 0)   # preview creates nothing
        res = self.post(self.base + 'cards/import/', {'markdown': CHAPTERS_MD, 'commit': True})
        self.assertEqual(res.json()['created'], 2)
        self.assertEqual(self.project.cards.first().takeaways, ['Point one', 'Point two'])
        self.post(self.base + 'cards/import/', {'markdown': CHAPTERS_MD, 'commit': True, 'replace': True})
        self.assertEqual(self.project.cards.count(), 2)   # replaced, not doubled

    def test_bad_import_creates_nothing(self):
        res = self.post(self.base + 'cards/import/', {'markdown': 'no markers here', 'commit': True})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(self.project.cards.count(), 0)

    def test_import_size_is_capped(self):
        res = self.post(self.base + 'cards/import/', {'markdown': 'x' * 300_001})
        self.assertEqual(res.status_code, 400)

    def test_import_parser_stays_fast_on_hostile_text(self):
        # The inputs CodeQL described for the old patterns; each used to take quadratic time.
        from projects.markdown_import import parse_markdown_cards
        hostile = [
            '<!-- CARD -->' + '<!--title:' + ' ' * 50_000,
            '<!-- CARD -->' + '<!--teaser:' + ' ' * 50_000,
            '<!--card-->' + '<!--card-->a' * 20_000,
            '<!-- CARD -->\n<!-- TITLE: t -->\n<!-- TEASER: t -->\nb\n<!-- TAKEAWAYS -->\n* ' + ' ' * 50_000 + '\n<!-- /CARD -->',
        ]
        for text in hostile:
            started = time.perf_counter()
            parse_markdown_cards(text)
            self.assertLess(time.perf_counter() - started, 0.5)

    def test_import_parser_reads_the_template_as_before(self):
        from projects.markdown_import import parse_markdown_cards
        text = ('<!-- /CARD --> stray\n<!-- card -->\n<!--TITLE:   Spaced title   -->\n<!-- TEASER: Tease -->\n'
                'Body\n<!-- TAKEAWAYS -->\n- One\n  *   Two  \n-not a bullet\n- \n<!-- /CARD -->\n<!-- CARD --> never closed')
        cards, errors = parse_markdown_cards(text)
        self.assertEqual(errors, [])
        self.assertEqual(len(cards), 1)
        self.assertEqual((cards[0].title, cards[0].teaser, cards[0].body), ('Spaced title', 'Tease', 'Body'))
        self.assertEqual(cards[0].takeaways_raw, 'One\nTwo\n')

    def test_export(self):
        ProjectCard.objects.create(project=self.project, title='Exported', teaser='T', body='Body')
        res = self.client.get(f'/studio/api/{self.base}cards/export/')
        self.assertIn('attachment', res['Content-Disposition'])
        self.assertIn('<!-- TITLE: Exported -->', res.content.decode())


TEST_SECRET = 'studio-test-secret'


def signed_ref(public_id, resource_type='image', fmt='jpg', version='1700000000', secret=TEST_SECRET):
    """The reference the browser sends after a direct upload, signed the way Cloudinary signs it."""
    import cloudinary.utils
    signature = cloudinary.utils.api_sign_request({'public_id': public_id, 'version': version}, secret)
    return f'{resource_type}/upload/v{version}/{public_id}.{fmt}#{signature}'


class MediaTests(StudioTestCase):
    def setUp(self):
        super().setUp()
        import cloudinary
        config = cloudinary.config()
        for key, value in (('api_secret', TEST_SECRET), ('api_key', '1234'), ('cloud_name', 'studio-test')):
            patcher = mock.patch.object(config, key, value, create=True)
            patcher.start()
            self.addCleanup(patcher.stop)

    def media(self, kind, rest=''):
        return f'{self.base}media/{kind}/{rest}'

    def test_sign_fixes_the_folder(self):
        data = self.post(self.media('photos', 'sign/')).json()
        self.assertEqual(data['params']['folder'], 'project_photos')
        self.assertIn('signature', data['params'])
        self.assertIn('/image/upload', data['upload_url'])
        self.assertIn('/video/upload', self.post(self.media('videos', 'sign/')).json()['upload_url'])
        self.assertEqual(self.post(self.media('embeds', 'sign/')).status_code, 404)
        self.assertEqual(self.post(self.media('scripts', 'sign/')).status_code, 404)

    def test_add_photo_and_video_from_verified_uploads(self):
        res = self.post(self.media('photos', 'new/'), {'ref': signed_ref('project_photos/abc')})
        self.assertEqual(res.status_code, 200, res.content)
        photo = self.project.photos.get()
        self.assertEqual(photo.image.public_id, 'project_photos/abc')
        self.assertIn('project_photos/abc', res.json()['item']['url'])
        res = self.post(self.media('videos', 'new/'), {'ref': signed_ref('project_videos/clip', 'video', 'mp4')})
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(self.project.videos.get().video.public_id, 'project_videos/clip')
        second = self.post(self.media('photos', 'new/'), {'ref': signed_ref('project_photos/def')}).json()['item']
        self.assertEqual(second['order'], photo.order + 1)

    def test_forged_or_misplaced_uploads_are_refused(self):
        cases = {
            'bad signature': ('photos', signed_ref('project_photos/abc', secret='wrong')),
            'not a reference': ('photos', 'https://evil.example/x.jpg'),
            'other folder': ('photos', signed_ref('thumbnails/abc')),
            'video as photo': ('photos', signed_ref('project_photos/abc', 'video', 'mp4')),
            'photo as video': ('videos', signed_ref('project_videos/abc', 'image')),
            'empty': ('photos', ''),
        }
        for name, (kind, ref) in cases.items():
            with self.subTest(name):
                self.assertEqual(self.post(self.media(kind, 'new/'), {'ref': ref}).status_code, 400)
        self.assertFalse(self.project.photos.exists() or self.project.videos.exists())

    def test_embeds_use_the_model_check(self):
        good = '<iframe width="560" src="https://www.youtube.com/embed/abc" allowfullscreen></iframe>'
        res = self.post(self.media('embeds', 'new/'), {'embed_code': good, 'caption': 'Trailer'})
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.json()['item']['src'], 'https://www.youtube.com/embed/abc')
        for bad in ('<iframe src="https://evil.example/x"></iframe>',
                    '<iframe src="https://www.youtube.com/embed/a"></iframe><script>alert(1)</script>',
                    '<iframe src="http://www.youtube.com/embed/a"></iframe>', ''):
            with self.subTest(bad):
                res = self.post(self.media('embeds', 'new/'), {'embed_code': bad})
                self.assertEqual(res.status_code, 400)
                self.assertIn('embed_code', res.json()['errors'])
        embed = self.project.embeds.get()
        res = self.post(self.media('embeds', f'{embed.pk}/'), {'embed_code': '<iframe src="https://evil.example/x"></iframe>'})
        self.assertIn('embed_code', res.json()['errors'])
        embed.refresh_from_db()
        self.assertEqual(embed.safe_src, 'https://www.youtube.com/embed/abc')   # unchanged
        self.assertEqual(self.post(self.media('embeds', f'{embed.pk}/'), {'safe_src': 'https://evil.example'}).status_code, 400)

    def test_caption_reorder_delete_and_ownership(self):
        from projects.models import ProjectPhoto
        a = ProjectPhoto.objects.create(project=self.project, image='project_photos/a', order=1)
        b = ProjectPhoto.objects.create(project=self.project, image='project_photos/b', order=2)
        theirs = ProjectPhoto.objects.create(project=self.other, image='project_photos/c', order=1)
        res = self.post(self.media('photos', f'{a.pk}/'), {'caption': 'Sunset'})
        self.assertEqual(res.json()['item']['caption'], 'Sunset')
        self.assertEqual(self.post(self.media('photos', f'{a.pk}/'), {'caption': 'x' * 201}).status_code, 400)
        self.assertEqual(self.post(self.media('photos', 'reorder/'), {'ids': [b.pk, a.pk]}).status_code, 200)
        self.assertEqual(list(self.project.photos.values_list('pk', flat=True)), [b.pk, a.pk])
        self.assertEqual(self.post(self.media('photos', 'reorder/'), {'ids': [b.pk, a.pk, theirs.pk]}).status_code, 400)
        self.assertEqual(self.post(self.media('photos', f'{theirs.pk}/'), {'caption': 'x'}).status_code, 404)
        self.assertEqual(self.post(self.media('photos', f'{theirs.pk}/delete/')).status_code, 404)
        self.post(self.media('photos', f'{a.pk}/delete/'))
        self.assertEqual(list(self.project.photos.values_list('pk', flat=True)), [b.pk])

    def test_state_lists_the_media(self):
        from projects.models import ProjectEmbed, ProjectPhoto
        ProjectPhoto.objects.create(project=self.project, image='project_photos/a', caption='A')
        ProjectEmbed.objects.create(project=self.project, embed_code='x', safe_src='https://evil.example', is_safe=False)
        data = self.get(self.base).json()
        self.assertEqual(data['counts'], {'photos': 1, 'videos': 0, 'embeds': 1})
        self.assertEqual(data['photos'][0]['caption'], 'A')
        self.assertEqual(data['embeds'][0]['src'], '')   # an embed that never passed the check gets no preview
        self.assertEqual(data['choices']['maxUploadMb'], {'photos': 10, 'videos': 100})


@override_settings(DEBUG=False, SECURE_SSL_REDIRECT=False)
class IndexNowThrottleTests(TestCase):
    def test_autosaves_ping_each_page_at_most_once_per_window(self):
        cache.clear()
        project = Projects.objects.create(name='Pinged', description='x', year=2025)
        with mock.patch('projects.indexnow.enabled', return_value=True), \
                mock.patch('projects.indexnow.submit_quietly') as submit:
            for i in range(5):
                with self.captureOnCommitCallbacks(execute=True):
                    project.description = f'edit {i}'
                    project.save()
        self.assertEqual(submit.call_count, 1)
