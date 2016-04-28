# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


def forward_project_grades_default(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    Project = apps.get_model('api', 'Project')
    default_grades_range = ['K', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12']

    Project.objects.using(db_alias).filter(
        grades_range__isnull=True
    ).update(
        grades_range=default_grades_range
    )

def backward_project_grades_default(apps, schema_editor):
    pass  #do nothing


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0060_merge'),
    ]

    operations = [
        migrations.RunPython(
            forward_project_grades_default,
            backward_project_grades_default
        )
    ]
