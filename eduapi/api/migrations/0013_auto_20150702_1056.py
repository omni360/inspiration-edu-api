# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0012_auto_20150630_1223'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='project',
            name='sys_message',
        ),
        migrations.AddField(
            model_name='project',
            name='lock_message',
            field=jsonfield.fields.JSONField(default={}, help_text=b'A system message that explains why this project is locked', blank=True),
            preserve_default=True,
        ),
    ]
