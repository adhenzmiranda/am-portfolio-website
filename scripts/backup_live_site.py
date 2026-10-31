"""
Back up the live site's content to this computer.

    python scripts/backup_live_site.py            # database + Cloudinary media
    python scripts/backup_live_site.py --no-media # database only

Run it from the project folder with the venv active, after `heroku login`.

What it saves (into backups/, which is gitignored):
  backups/<date-time>/data.json  every project, photo/video/embed/card record,
                                 category, Experience/Education entry and the
                                 admin user, read from the live Neon database.
                                 2FA device secrets, sessions and logs are left out.
  backups/media/                 every image and video file on Cloudinary.
                                 Shared by all backups; files already downloaded
                                 are skipped, so later runs only fetch new ones.

It only reads: nothing on Heroku, Neon or Cloudinary is changed. The live
DATABASE_URL is fetched with the Heroku CLI and only passed to the dumpdata
process; it is never written to disk.

To restore into a fresh database:
  1. Point DATABASE_URL at the new, empty database.
  2. python manage.py migrate
  3. python manage.py loaddata backups/<date-time>/data.json
  4. If the Cloudinary account itself was lost, re-upload backups/media/ to a
     new account keeping the same folder/file names (they are the public IDs
     the database refers to), then update the CLOUDINARY_* config vars.
"""
import argparse
import os
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEROKU_APP = 'am04'
EXCLUDE = [
    'contenttypes', 'auth.permission', 'sessions', 'admin.logentry',
    'otp_totp', 'otp_static',  # 2FA secrets: re-register a device after a restore instead
]


def live_database_url():
    heroku = shutil.which('heroku')
    if not heroku:
        sys.exit('The Heroku CLI was not found. Install it, run `heroku login`, then try again.')
    result = subprocess.run([heroku, 'config:get', 'DATABASE_URL', '-a', HEROKU_APP],
                            capture_output=True, text=True)
    url = result.stdout.strip()
    if result.returncode != 0 or not url.startswith('postgres'):
        sys.exit(f'Could not read DATABASE_URL from Heroku app {HEROKU_APP!r}. Run `heroku login` and try again.\n{result.stderr.strip()}')
    return url


def dump_database(out_file, database_url=None):
    env = dict(os.environ)
    env['PYTHONUTF8'] = '1'  # Windows otherwise writes the file as cp1252 and fails on emoji
    if database_url:
        env['DATABASE_URL'] = database_url
    cmd = [sys.executable, 'manage.py', 'dumpdata', '--natural-foreign', '--natural-primary',
           '--indent', '2', '-o', str(out_file)]
    for label in EXCLUDE:
        cmd += ['--exclude', label]
    subprocess.run(cmd, cwd=ROOT, env=env, check=True)


def cloudinary_resources():
    """Yield every uploaded image, video and raw file in the Cloudinary account."""
    import cloudinary
    import cloudinary.api
    from dotenv import load_dotenv

    load_dotenv(ROOT / '.env')
    cloudinary.config(
        cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
        api_key=os.getenv('CLOUDINARY_API_KEY'),
        api_secret=os.getenv('CLOUDINARY_API_SECRET'),
        secure=True,
    )
    for resource_type in ('image', 'video', 'raw'):
        cursor = None
        while True:
            page = cloudinary.api.resources(resource_type=resource_type, type='upload',
                                            max_results=500, next_cursor=cursor)
            yield from page.get('resources', [])
            cursor = page.get('next_cursor')
            if not cursor:
                break


def download_media(media_dir):
    downloaded = skipped = failed = 0
    for res in cloudinary_resources():
        name = res['public_id'] + (f".{res['format']}" if res.get('format') else '')
        target = media_dir / res['resource_type'] / name
        if target.exists() and target.stat().st_size == res.get('bytes', -1):
            skipped += 1
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            urllib.request.urlretrieve(res['secure_url'], target)
            downloaded += 1
            print(f'  downloaded {res["resource_type"]}/{name}')
        except Exception as exc:  # keep going; report at the end
            failed += 1
            print(f'  FAILED {res["resource_type"]}/{name}: {exc}')
    return downloaded, skipped, failed


def main():
    parser = argparse.ArgumentParser(description='Back up the live site (database + Cloudinary media).')
    parser.add_argument('--no-media', action='store_true', help='only back up the database')
    parser.add_argument('--local', action='store_true', help='dump the local development database instead (for testing)')
    args = parser.parse_args()

    backups = ROOT / 'backups'
    run_dir = backups / datetime.now().strftime('%Y-%m-%d_%H%M')
    run_dir.mkdir(parents=True, exist_ok=True)

    print('Backing up the database...')
    dump_database(run_dir / 'data.json', None if args.local else live_database_url())
    print(f'  saved {run_dir / "data.json"}')

    if not args.no_media:
        print('Backing up Cloudinary media (only new files are downloaded)...')
        downloaded, skipped, failed = download_media(backups / 'media')
        print(f'  {downloaded} downloaded, {skipped} already backed up, {failed} failed')
        if failed:
            print('  Run the script again to retry the failed files.')

    print('Done. Keep a copy of the backups folder somewhere else too (an external drive or cloud storage).')


if __name__ == '__main__':
    main()
