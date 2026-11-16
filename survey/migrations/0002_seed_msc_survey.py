from django.db import migrations


def load_survey(apps, schema_editor):
    from survey.seed import load
    load(apps)


class Migration(migrations.Migration):
    """Creates "Think Before You Prompt" at /msc-survey/ as a Draft (see survey/seed.py)."""

    dependencies = [
        ('survey', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(load_survey, migrations.RunPython.noop),
    ]
