# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django_counter_field.fields


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0005_auto_20150507_1729'),
    ]

    operations = [
        migrations.AddField(
            model_name='lesson',
            name='students_count',
            field=django_counter_field.fields.CounterField(default=0),
            preserve_default=True,
        ),
    ]
