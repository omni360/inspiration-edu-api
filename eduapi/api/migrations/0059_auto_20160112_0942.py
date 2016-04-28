# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.contrib.postgres.fields


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0058_igniteuser_parent_email'),
    ]

    operations = [
        migrations.AlterField(
            model_name='project',
            name='learning_objectives',
            field=django.contrib.postgres.fields.ArrayField(size=None, null=True, base_field=models.CharField(max_length=100), blank=True),
        ),
        migrations.AlterField(
            model_name='project',
            name='skills_acquired',
            field=django.contrib.postgres.fields.ArrayField(size=None, null=True, base_field=models.CharField(max_length=100), blank=True),
        ),
    ]
