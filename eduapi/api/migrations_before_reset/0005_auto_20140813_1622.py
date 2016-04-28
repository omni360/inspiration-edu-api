# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0004_teachersfilecourselink_teachersfilelessonlink'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='igniteuser',
            options={},
        ),
        migrations.RemoveField(
            model_name='igniteuser',
            name='date_joined',
        ),
        migrations.RemoveField(
            model_name='igniteuser',
            name='first_name',
        ),
        migrations.RemoveField(
            model_name='igniteuser',
            name='last_name',
        ),
        migrations.RemoveField(
            model_name='igniteuser',
            name='username',
        ),
    ]
