# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django_counter_field.fields


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0003_auto_20150324_1120'),
    ]

    operations = [
        migrations.AddField(
            model_name='classroom',
            name='projects_count',
            field=django_counter_field.fields.CounterField(default=0),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='classroom',
            name='students_approved_count',
            field=django_counter_field.fields.CounterField(default=0),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='classroom',
            name='students_pending_count',
            field=django_counter_field.fields.CounterField(default=0),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='classroom',
            name='students_rejected_count',
            field=django_counter_field.fields.CounterField(default=0),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='lesson',
            name='steps_count',
            field=django_counter_field.fields.CounterField(default=0),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='project',
            name='lesson_count',
            field=django_counter_field.fields.CounterField(default=0),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='project',
            name='students_count',
            field=django_counter_field.fields.CounterField(default=0),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='projectstate',
            name='completed_lessons_count',
            field=django_counter_field.fields.CounterField(default=0),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='projectstate',
            name='enrolled_lessons_count',
            field=django_counter_field.fields.CounterField(default=0),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='step',
            name='instructions_count',
            field=django_counter_field.fields.CounterField(default=0),
            preserve_default=True,
        ),
    ]
