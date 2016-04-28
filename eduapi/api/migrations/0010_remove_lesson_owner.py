# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0009_auto_20150601_1351'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='lesson',
            name='owner',
        ),
    ]
