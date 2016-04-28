# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0014_auto_20150707_1343'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='current_editor_id',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
