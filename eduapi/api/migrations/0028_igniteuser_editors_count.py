# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django_counter_field.fields


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0027_auto_20150816_1048'),
    ]

    operations = [
        migrations.AddField(
            model_name='igniteuser',
            name='editors_count',
            field=django_counter_field.fields.CounterField(default=0),
        ),
    ]
