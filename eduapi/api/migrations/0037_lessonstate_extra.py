# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0036_auto_20150827_1024'),
    ]

    operations = [
        migrations.AddField(
            model_name='lessonstate',
            name='extra',
            field=jsonfield.fields.JSONField(help_text=b'Stores user specific data, e.g. canvas ID for Tinkercad', null=True, blank=True),
        ),
    ]
