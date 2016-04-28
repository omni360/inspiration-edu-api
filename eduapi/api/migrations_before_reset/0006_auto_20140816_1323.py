# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0005_auto_20140813_1622'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='igniteuser',
            options={},
        ),
        migrations.AddField(
            model_name='course',
            name='owner',
            field=models.ForeignKey(default=2, to=settings.AUTH_USER_MODEL),
            preserve_default=False,
        ),
    ]
