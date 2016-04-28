# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0037_auto_20141011_1914'),
    ]

    operations = [
        migrations.AddField(
            model_name='igniteuser',
            name='is_verified_adult',
            field=models.BooleanField(default=False, help_text=b'Was the user verified as an adult'),
            preserve_default=True,
        ),
    ]
