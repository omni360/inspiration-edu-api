# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0033_auto_20140927_1719'),
    ]

    operations = [
        migrations.AddField(
            model_name='classroom',
            name='students',
            field=models.ManyToManyField(related_name=b'classrooms', through='api.ClassroomState', to=settings.AUTH_USER_MODEL),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='classroomstate',
            name='user',
            field=models.ForeignKey(related_name=b'classrooms_states', to=settings.AUTH_USER_MODEL),
        ),
    ]
