# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0049_auto_20151119_1452'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='is_searchable',
            field=models.BooleanField(default=True, help_text=b'Whether the object will be searchable in list of projects'),
        ),
        migrations.RemoveField(
            model_name='project',
            name='is_hidden',
        ),
    ]
