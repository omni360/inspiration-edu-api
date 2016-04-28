# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import jsonfield.fields
import api.models.fields

import json


def forwards_fix_array_json_fields(apps, schema_editor):
    Project = apps.get_model('api', 'Project')
    Lesson = apps.get_model('api', 'Lesson')
    Step = apps.get_model('api', 'Step')

    fix_fields = (
        (Project, 'teachers_files_list'),
        (Project, 'video_links_list'),
        (Lesson, 'teachers_files_list'),
        (Step, 'instructions_list'),
    )

    for model, field_name in fix_fields:
        objects_to_fix = model.objects.filter(**{
            '{}__isnull'.format(field_name): False,
        })

        for obj in objects_to_fix:
            value = getattr(obj, field_name)
            fixed_value = []
            for v in value:
                # print 'old', v
                while isinstance(v, (str, unicode)):
                    v = json.loads(v)
                fixed_value.append(v)
                # print 'fixed:', v
                # key = raw_input('... (press enter or q to quit)')
                # if key == 'q':
                #     break
                # continue
            setattr(obj, field_name, fixed_value)
            obj.save(update_fields=[field_name])

def backwards_fix_array_json_fields(apps, schema_editor):
    pass  # do nothing


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0044_classroom_is_archived'),
    ]

    operations = [
        migrations.RunPython(
            forwards_fix_array_json_fields,
            backwards_fix_array_json_fields
        ),

        migrations.AlterField(
            model_name='lesson',
            name='teachers_files_list',
            field=api.models.fields.ArrayJSONField(size=None, null=True, base_field=jsonfield.fields.JSONField(), blank=True),
        ),
        migrations.AlterField(
            model_name='project',
            name='teachers_files_list',
            field=api.models.fields.ArrayJSONField(size=None, null=True, base_field=jsonfield.fields.JSONField(), blank=True),
        ),
        migrations.AlterField(
            model_name='project',
            name='video_links_list',
            field=api.models.fields.ArrayJSONField(size=None, null=True, base_field=jsonfield.fields.JSONField(), blank=True),
        ),
        migrations.AlterField(
            model_name='step',
            name='instructions_list',
            field=api.models.fields.ArrayJSONField(size=None, null=True, base_field=jsonfield.fields.JSONField(), blank=True),
        ),
    ]
