# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


def forward_current_editor_fk(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    Project = apps.get_model('api', 'Project')

    Project.objects.using(db_alias).filter(
        current_editor_id_old__gt=0
    ).update(
        current_editor_id=models.F('current_editor_id_old')
    )

def backward_current_editor_fk(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    Project = apps.get_model('api', 'Project')

    Project.objects.using(db_alias).filter(
        current_editor_id__isnull=False
    ).update(
        current_editor_id_old=models.F('current_editor_id')
    )


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0028_igniteuser_editors_count'),
    ]

    igniteuser_table = 'api_igniteuser'

    operations = [
        migrations.RenameField(
            model_name='project',
            old_name='current_editor_id',
            new_name='current_editor_id_old',
        ),
        migrations.AddField(
            model_name='project',
            name='current_editor',
            field=models.ForeignKey(related_name='current_edit_projects', to=settings.AUTH_USER_MODEL, null=True),
        ),

        # Copy current_editor_id from old to FK:
        migrations.RunPython(
            forward_current_editor_fk,
            backward_current_editor_fk
        ),

        migrations.RemoveField(
            model_name='project',
            name='current_editor_id_old',
        ),
    ]
