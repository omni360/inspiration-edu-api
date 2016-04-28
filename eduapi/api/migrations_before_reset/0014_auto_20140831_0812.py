# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0013_auto_20140831_0756'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='igniteuser',
            options={},
        ),
        migrations.RenameField(
            model_name='review',
            old_name='author',
            new_name='owner',
        ),
    ]
