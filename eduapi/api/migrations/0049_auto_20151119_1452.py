# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0048_merge'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='is_hidden',
            field=models.BooleanField(default=False, help_text=b'Whether the object will be hidden in list of projects'),
        ),
    ]
