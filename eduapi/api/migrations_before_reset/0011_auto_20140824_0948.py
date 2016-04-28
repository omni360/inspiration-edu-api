# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0010_auto_20140820_0816'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='igniteuser',
            options={},
        ),
        migrations.AddField(
            model_name='lessonstate',
            name='completed_steps',
            field=models.ManyToManyField(to=b'api.Step', through='api.StepState'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='stepstate',
            name='lesson_state',
            field=models.ForeignKey(default=1, to='api.LessonState'),
            preserve_default=False,
        ),
        migrations.RemoveField(
            model_name='lessonstate',
            name='steps',
        ),
    ]
