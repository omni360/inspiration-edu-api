# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0077_auto_20150224_1335'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lessonstate',
            name='project_state',
            field=models.ForeignKey(related_name='lesson_states', to='api.ProjectState'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='lessonstate',
            unique_together=set([('project_state', 'lesson')]),
        ),
        migrations.RemoveField(
            model_name='lessonstate',
            name='user',
        ),
    ]
