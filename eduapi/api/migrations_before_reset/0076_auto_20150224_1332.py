# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0075_auto_20150224_1310'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='classroomstate',
            name='projects',
        ),
        migrations.RemoveField(
            model_name='projectstate',
            name='lessons',
        ),
        migrations.AlterField(
            model_name='stepstate',
            name='lesson_state',
            field=models.ForeignKey(related_name='step_states', to='api.LessonState'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='lessonstate',
            name='project_state',
            field=models.ForeignKey(related_name='lesson_states', default=None, to='api.ProjectState', null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='lessonstate',
            name='user',
            field=models.ForeignKey(related_name='lessons', default=None, to=settings.AUTH_USER_MODEL, null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='projectstate',
            name='viewed_lessons',
            field=models.ManyToManyField(to='api.Lesson', through='api.LessonState'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='lessonstate',
            unique_together=set([('project_state', 'lesson'), ('user', 'lesson')]),
        ),
        migrations.RemoveField(
            model_name='lessonstate',
            name='joinURL',
        ),
        migrations.RemoveField(
            model_name='lessonstate',
            name='application_id',
        ),
        migrations.RemoveField(
            model_name='lessonstate',
            name='active',
        ),
    ]
