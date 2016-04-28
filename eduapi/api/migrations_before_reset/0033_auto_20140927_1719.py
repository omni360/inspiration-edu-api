# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0032_classroom_base_course'),
    ]

    operations = [
        migrations.AlterField(
            model_name='classroom',
            name='base_course',
            field=models.ForeignKey(related_name=b'derived_classes', blank=True, to='api.Course', help_text=b'The course that this class is based on', null=True),
        ),
    ]
