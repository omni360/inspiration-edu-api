# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0035_auto_20150830_0814'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='lesson',
            name='age',
        ),
        migrations.RemoveField(
            model_name='lesson',
            name='difficulty',
        ),
        migrations.RemoveField(
            model_name='lesson',
            name='license',
        ),
    ]
