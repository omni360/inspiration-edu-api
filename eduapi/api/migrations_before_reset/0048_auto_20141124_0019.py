# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0047_auto_20141123_2300'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='classroomstate',
            name='lessons',
        ),
        migrations.AddField(
            model_name='classroomstate',
            name='courses',
            field=models.ManyToManyField(to='api.CourseState'),
            preserve_default=True,
        ),
    ]
