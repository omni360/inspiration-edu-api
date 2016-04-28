# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0060_auto_20150112_1438'),
    ]

    operations = [
        migrations.AddField(
            model_name='lessonstate',
            name='is_completed',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='projectstate',
            name='is_completed',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
    ]
