# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import jsonfield.fields


def application_blob_to_object(apps, schema_editor):
    '''
    Updates application blob to be JSON object only.
    '''
    db_alias = schema_editor.connection.alias
    Lesson = apps.get_model('api', 'Lesson')
    Step = apps.get_model('api', 'Step')

    Lesson.objects.using(db_alias).exclude(application_blob__startswith='{').update(application_blob={})
    Step.objects.using(db_alias).exclude(application_blob__startswith='{').update(application_blob={})

def no_operation_callable(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lesson',
            name='application_blob',
            field=jsonfield.fields.JSONField(default={}, help_text=b"A JSON field that stores application specific data for presenting this step. It's recommended to use a URL", blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='step',
            name='application_blob',
            field=jsonfield.fields.JSONField(default={}, help_text=b"A JSON field that stores application specific data for presenting this step. It's recommended to use a URL", blank=True),
            preserve_default=True,
        ),

        migrations.RunPython(
            code=application_blob_to_object,
            reverse_code=no_operation_callable
        )
    ]
