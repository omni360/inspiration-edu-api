# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0031_igniteuser_user_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='classroom',
            name='is_deleted',
            field=models.BooleanField(default=False, db_index=True),
        ),
        migrations.AddField(
            model_name='lesson',
            name='is_deleted',
            field=models.BooleanField(default=False, db_index=True),
        ),
        migrations.AddField(
            model_name='project',
            name='is_deleted',
            field=models.BooleanField(default=False, db_index=True),
        ),
        migrations.AddField(
            model_name='step',
            name='is_deleted',
            field=models.BooleanField(default=False, db_index=True),
        ),
    ]
