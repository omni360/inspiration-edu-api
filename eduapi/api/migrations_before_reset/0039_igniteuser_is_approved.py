# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0038_igniteuser_is_verified_adult'),
    ]

    operations = [
        migrations.AddField(
            model_name='igniteuser',
            name='is_approved',
            field=models.BooleanField(default=False, help_text=b'Does the user have a guardian'),
            preserve_default=True,
        ),
    ]
