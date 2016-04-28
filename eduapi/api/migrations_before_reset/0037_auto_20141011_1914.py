# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0036_igniteuser_oxygen_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='igniteuser',
            name='oxygen_id',
            field=models.CharField(help_text=b'The Oxygen Member ID', unique=True, max_length=50),
        ),
    ]
