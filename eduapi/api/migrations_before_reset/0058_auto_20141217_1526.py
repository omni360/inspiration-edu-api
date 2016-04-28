# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0057_auto_20141215_1447'),
    ]

    operations = [
        migrations.AlterField(
            model_name='igniteuser',
            name='guardians',
            field=models.ManyToManyField(related_name='children', to=settings.AUTH_USER_MODEL, blank=True),
            preserve_default=True,
        ),
    ]
