# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0042_igniteuser_description'),
    ]

    operations = [
        migrations.AddField(
            model_name='course',
            name='tags',
            field=models.CharField(max_length=150, null=True, blank=True),
            preserve_default=True,
        ),
    ]
