# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import utils_app.hash


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0018_auto_20150719_1408'),
    ]

    operations = [
        migrations.AlterField(
            model_name='classroominvite',
            name='hash',
            field=models.CharField(default=utils_app.hash.generate_hash, unique=True, max_length=40),
        ),
        migrations.AlterField(
            model_name='delegateinvite',
            name='hash',
            field=models.CharField(default=utils_app.hash.generate_hash, unique=True, max_length=40),
        ),
        migrations.AlterField(
            model_name='viewinvite',
            name='hash',
            field=models.CharField(default=utils_app.hash.generate_hash, unique=True, max_length=40),
        ),
    ]
