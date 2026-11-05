"""
IndexNow (https://www.indexnow.org): tells Bing (and Yandex, Seznam, Naver)
straight away which URLs were added or changed, instead of waiting for them
to crawl. Free. Enabled only when the INDEXNOW_KEY setting is set; the key
is also served at /<key>.txt so the search engines can verify the site.
"""
import json
import logging
import urllib.error
import urllib.request
from urllib.parse import urlparse

from django.conf import settings

logger = logging.getLogger(__name__)

ENDPOINT = 'https://api.indexnow.org/indexnow'


def enabled():
    return bool(settings.INDEXNOW_KEY)


def submit(urls):
    """POST up to 10,000 absolute URLs on SITE_URL. Returns the HTTP status (200/202 = accepted)."""
    payload = json.dumps({
        'host': urlparse(settings.SITE_URL).netloc,
        'key': settings.INDEXNOW_KEY,
        'keyLocation': f'{settings.SITE_URL}/{settings.INDEXNOW_KEY}.txt',
        'urlList': list(urls)[:10000],
    }).encode()
    request = urllib.request.Request(ENDPOINT, data=payload, method='POST',
                                     headers={'Content-Type': 'application/json; charset=utf-8'})
    try:
        with urllib.request.urlopen(request, timeout=5) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:  # 400 bad request, 403 key not valid, 422 URLs not on host, 429 too many
        return exc.code


def submit_quietly(urls):
    """For saves in the admin: never let a ping failure break the save."""
    if not enabled():
        return
    try:
        status = submit(urls)
        if status not in (200, 202):
            logger.warning('IndexNow rejected %s (HTTP %s)', urls, status)
    except Exception:
        logger.exception('IndexNow ping failed')
