from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0037_remove_projects_technologies_delete_technology_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='projects',
            name='display_mode',
            field=models.CharField(
                choices=[('portfolio', 'Portfolio'), ('blogpost', 'Blog Post')],
                default='portfolio',
                help_text='Portfolio: media shown in separate sections. Blog Post: description is the main content with inline images via markdown.',
                max_length=20,
            ),
        ),
    ]
