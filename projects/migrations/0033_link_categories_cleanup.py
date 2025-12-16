# Migration to copy temp_category_id to category FK and cleanup

from django.db import migrations


def link_categories(apps, schema_editor):
    """Link projects to their categories using the temp field"""
    Projects = apps.get_model('projects', 'Projects')
    Category = apps.get_model('projects', 'Category')
    
    for project in Projects.objects.all():
        if project.temp_category_id:
            try:
                category = Category.objects.get(id=project.temp_category_id)
                project.category = category
                project.save(update_fields=['category'])
            except Category.DoesNotExist:
                pass


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0032_category_alter_projects_category'),
    ]

    operations = [
        # Link the categories using temp field
        migrations.RunPython(link_categories, migrations.RunPython.noop),
        # Remove temp field
        migrations.RemoveField(
            model_name='projects',
            name='temp_category_id',
        ),
    ]
