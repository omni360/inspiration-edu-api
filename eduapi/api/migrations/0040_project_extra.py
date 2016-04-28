# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0039_auto_20151011_0705'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='extra',
            field=jsonfield.fields.JSONField(help_text=b'Extra data for the project and its lessons.', null=True, blank=True),
        ),
    ]
