# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


def forward_project_publish_date(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    Project = apps.get_model('api', 'Project')

    Project.objects.using(db_alias).filter(
        publish_mode='published'
    ).update(
        publish_date=models.F('updated')
    )

def backward_project_publish_date(apps, schema_editor):
    pass  #do nothing


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0042_auto_20151025_1445'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='publish_date',
            field=models.DateTimeField(db_index=True, null=True, blank=True),
        ),

        # Initialize publish_date with updated field:
        migrations.RunPython(
            forward_project_publish_date,
            backward_project_publish_date
        )
    ]
