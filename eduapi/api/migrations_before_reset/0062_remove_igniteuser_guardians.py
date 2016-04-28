# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0061_auto_20150121_1634'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='igniteuser',
            name='guardians',
        ),
        migrations.AddField(
            model_name='igniteuser',
            name='guardians',
            field=models.ManyToManyField(related_name='children', through='api.ChildGuardian', to=settings.AUTH_USER_MODEL, blank=True),
            preserve_default=True,
        ),
    ]
