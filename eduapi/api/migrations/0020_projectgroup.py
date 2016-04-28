# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.contrib.postgres.fields


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0019_auto_20150720_0830'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProjectGroup',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('group_name', models.CharField(unique=True, max_length=15)),
                ('projects', django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(verbose_name=b'Projects IDs'), size=None)),
            ],
        ),
    ]
