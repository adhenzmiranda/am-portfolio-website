"""Who may use Studio: staff who are fully logged in to the admin (password + 2FA)."""
from functools import wraps

from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme, urlencode


def is_studio_user(request):
    user = getattr(request, 'user', None)
    if not (user and user.is_authenticated and user.is_staff):
        return False
    is_verified = getattr(user, 'is_verified', None)
    return bool(is_verified and is_verified())


def _private(response):
    response['X-Robots-Tag'] = 'noindex, nofollow'
    response['Cache-Control'] = 'no-store'
    return response


def studio_page(view):
    """Pages: send anyone else to the admin login, then back here."""
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not is_studio_user(request):
            target = request.get_full_path()
            if not url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()},
                                                   require_https=request.is_secure()):
                target = reverse('studio:dashboard')
            return redirect(f"{reverse('admin:login')}?{urlencode({'next': target})}")
        get_token(request)   # sets the CSRF cookie the API calls send back
        return _private(view(request, *args, **kwargs))
    return wrapped


def studio_api(view):
    """API calls: a JSON 403 for anyone else (e.g. an expired login)."""
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not is_studio_user(request):
            return _private(JsonResponse(
                {'error': 'Your admin login has expired. Log in again in another tab, then retry.'}, status=403))
        return _private(view(request, *args, **kwargs))
    return wrapped
