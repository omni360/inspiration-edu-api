# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0017_auto_20140902_0754'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='igniteuser',
            options={},
        ),
        migrations.RemoveField(
            model_name='course',
            name='materials',
        ),
        migrations.RemoveField(
            model_name='course',
            name='tools',
        ),
    ]
