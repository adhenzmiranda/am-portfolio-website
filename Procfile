release: python manage.py migrate --noinput
web: gunicorn projects.wsgi --log-file - 