# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0017_auto_20150719_1101'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='lesson',
            name='teacher_info',
        ),
        migrations.AlterField(
            model_name='viewinvite',
            name='hash',
            field=models.CharField(default=b'JIY2ELl6XsOlbvMFaCBV3mr8ChxYBPmtZKkmXjlc', unique=True, max_length=40),
        ),
    ]
