from django.conf import settings
from django.http import HttpResponsePermanentRedirect


class CanonicalDomainRedirectMiddleware:
    """
    Permanently redirects requests for any host in settings.REDIRECT_HOSTS
    (e.g. the raw herokuapp.com address) to settings.CANONICAL_HOST, keeping
    the same path and query string. This keeps all traffic behind
    Cloudflare, which the contact form's rate limiter relies on.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().split(':')[0]
        redirect_hosts = getattr(settings, 'REDIRECT_HOSTS', [])
        canonical_host = getattr(settings, 'CANONICAL_HOST', None)
        if canonical_host and host in redirect_hosts:
            redirect_url = f'https://{canonical_host}{request.get_full_path()}'
            return HttpResponsePermanentRedirect(redirect_url)
        return self.get_response(request)
