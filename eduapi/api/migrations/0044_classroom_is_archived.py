# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0043_project_publish_date'),
    ]

    operations = [
        migrations.AddField(
            model_name='classroom',
            name='is_archived',
            field=models.BooleanField(default=False, help_text=b'Flag whether the classroom is archived'),
        ),
    ]
