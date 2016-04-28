# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import jsonfield.fields
import api.models.fields


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0054_igniteuser_show_authoring_tooltips'),
    ]

    operations = [
        migrations.AddField(
            model_name='classroom',
            name='projects_separators',
            field=api.models.fields.ArrayJSONField(size=None, null=True, base_field=jsonfield.fields.JSONField(), blank=True),
        ),
    ]
