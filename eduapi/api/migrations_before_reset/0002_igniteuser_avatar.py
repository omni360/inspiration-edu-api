# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='igniteuser',
            name='avatar',
            field=models.CharField(help_text=b"The URL of the user's avatar", max_length=300, null=True, blank=True),
            preserve_default=True,
        ),
    ]
