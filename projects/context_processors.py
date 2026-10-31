from django.conf import settings


def site_url(request):
    """Expose the canonical site URL (no trailing slash) to every template."""
    return {'SITE_URL': settings.SITE_URL}
