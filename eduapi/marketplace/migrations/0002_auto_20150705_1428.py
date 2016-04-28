# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('marketplace', '0001_initial'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='purchase',
            unique_together=set([('project', 'user')]),
        ),
    ]
