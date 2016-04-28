# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0009_auto_20140820_0812'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='igniteuser',
            options={},
        ),
        migrations.AddField(
            model_name='lessonstate',
            name='user',
            field=models.ForeignKey(default=4, to=settings.AUTH_USER_MODEL),
            preserve_default=False,
        ),
    ]
