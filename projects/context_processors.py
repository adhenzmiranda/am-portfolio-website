import os
import subprocess
from datetime import datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

from django.conf import settings

# The footer date is shown in the owner's local time, not the server's UTC.
DISPLAY_TZ = ZoneInfo('Asia/Dubai')


def site_url(request):
    """Expose the canonical site URL (no trailing slash) to every template."""
    return {'SITE_URL': settings.SITE_URL}


@lru_cache(maxsize=1)
def _last_updated():
    """Date (in Dubai time) the running code was last released, or None if unknown.

    On Heroku this is the release time from dyno metadata
    (`heroku labs:enable runtime-dyno-metadata`), which provides
    HEROKU_RELEASE_CREATED_AT. Locally it falls back to the latest git commit.
    Worked out once per process, since it can't change while the process runs.
    """
    raw = os.getenv('HEROKU_RELEASE_CREATED_AT')
    if not raw:
        try:
            raw = subprocess.run(
                ['git', 'log', '-1', '--format=%cI'],
                cwd=settings.BASE_DIR, capture_output=True, text=True, timeout=5, check=True,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return None
    try:
        # A plain date, so templates don't convert it back to the server's UTC.
        return datetime.fromisoformat(raw).astimezone(DISPLAY_TZ).date()
    except ValueError:
        return None


def site_last_updated(request):
    """Expose SITE_LAST_UPDATED (a date in Dubai time, or None) to every template."""
    return {'SITE_LAST_UPDATED': _last_updated()}
