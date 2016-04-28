# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0006_auto_20140816_1323'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='igniteuser',
            options={},
        ),
        migrations.AddField(
            model_name='lesson',
            name='owner',
            field=models.ForeignKey(default=2, to=settings.AUTH_USER_MODEL),
            preserve_default=False,
        ),
    ]
