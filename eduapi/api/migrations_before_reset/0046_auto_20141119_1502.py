# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import api.models.fields


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0045_auto_20141118_1440'),
    ]

    operations = [
        migrations.AlterField(
            model_name='course',
            name='tags',
            field=api.models.fields.TagsField(default=b'', max_length=150, blank=True),
            preserve_default=True,
        ),
    ]
