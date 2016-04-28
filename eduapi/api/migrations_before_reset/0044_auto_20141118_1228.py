# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0043_course_tags'),
    ]

    operations = [
        migrations.AlterField(
            model_name='course',
            name='tags',
            field=models.CharField(default=b'', max_length=150, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='igniteuser',
            name='description',
            field=models.CharField(default=b'', help_text=b'The description of the user', max_length=500, blank=True),
            preserve_default=True,
        ),
    ]
