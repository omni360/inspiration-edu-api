# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0070_merge'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='step',
            name='type',
        ),
    ]
