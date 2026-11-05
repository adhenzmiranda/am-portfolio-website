from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from projects import indexnow
from projects.sitemaps import sitemaps


class Command(BaseCommand):
    help = 'Submit every URL in the sitemap (or the URLs given) to IndexNow, e.g. after a big update.'

    def add_arguments(self, parser):
        parser.add_argument('urls', nargs='*', help='absolute URLs to submit (default: the whole sitemap)')

    def handle(self, *args, urls, **options):
        if not indexnow.enabled():
            raise CommandError('INDEXNOW_KEY is not set.')
        if not urls:
            for sitemap in sitemaps.values():
                s = sitemap()
                urls += [settings.SITE_URL + s.location(item) for item in s.items()]
        status = indexnow.submit(urls)
        if status in (200, 202):
            self.stdout.write(self.style.SUCCESS(f'IndexNow accepted {len(urls)} URLs (HTTP {status}).'))
        else:
            raise CommandError(f'IndexNow returned HTTP {status} for {len(urls)} URLs.')
