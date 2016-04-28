# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('marketplace', '0002_auto_20150705_1428'),
    ]

    operations = [
        migrations.AlterField(
            model_name='purchase',
            name='added',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
    ]
