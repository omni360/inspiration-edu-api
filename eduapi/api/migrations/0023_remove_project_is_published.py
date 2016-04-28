# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0022_merge'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='project',
            name='is_published',
        ),
    ]
