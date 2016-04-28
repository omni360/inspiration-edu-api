# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0007_auto_20140816_1440'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='igniteuser',
            options={},
        ),
        migrations.RemoveField(
            model_name='step',
            name='is_deleted',
        ),
    ]
