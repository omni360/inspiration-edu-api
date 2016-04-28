# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0038_auto_20151008_0734'),
    ]

    operations = [
        migrations.AddField(
            model_name='lessonstate',
            name='user',
            field=models.ForeignKey(related_name='lessons', blank=True, to=settings.AUTH_USER_MODEL, null=True),
        ),
        migrations.AddField(
            model_name='stepstate',
            name='user',
            field=models.ForeignKey(related_name='steps', blank=True, to=settings.AUTH_USER_MODEL, null=True),
        ),
    ]
