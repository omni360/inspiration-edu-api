# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0041_auto_20141106_1307'),
    ]

    operations = [
        migrations.AddField(
            model_name='igniteuser',
            name='description',
            field=models.CharField(help_text=b'The description of the user', max_length=500, null=True, blank=True),
            preserve_default=True,
        ),
    ]
