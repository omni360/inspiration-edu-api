# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0053_auto_20151215_1221'),
    ]

    operations = [
        migrations.AddField(
            model_name='igniteuser',
            name='show_authoring_tooltips',
            field=models.BooleanField(default=True, help_text=b'Flag whether to show user authoring tooltips in ProjectIgnite'),
        ),
    ]
