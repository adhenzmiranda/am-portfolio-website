from urllib.parse import urlparse

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Projects


class SiteURLSitemap(Sitemap):
    """
    Builds every URL from settings.SITE_URL instead of the Sites framework,
    so the sitemap always lists https://adhenzmiranda.com/... no matter
    which host the request came in on.
    """
    protocol = urlparse(settings.SITE_URL).scheme

    def get_domain(self, site=None):
        return urlparse(settings.SITE_URL).netloc


class StaticViewSitemap(SiteURLSitemap):
    changefreq = 'monthly'

    def items(self):
        return ['home', 'about', 'projects_page', 'contact']

    def location(self, item):
        return reverse(item)


class ProjectsSitemap(SiteURLSitemap):
    changefreq = 'monthly'

    def items(self):
        return Projects.objects.order_by('-year', 'id')

    def lastmod(self, obj):
        return obj.updated_at


sitemaps = {
    'static': StaticViewSitemap,
    'projects': ProjectsSitemap,
}
