# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0020_auto_20140904_1125'),
    ]

    operations = [
        migrations.AddField(
            model_name='igniteuser',
            name='guardian',
            field=models.ForeignKey(related_name=b'wards', blank=True, to=settings.AUTH_USER_MODEL, null=True),
            preserve_default=True,
        ),
    ]
