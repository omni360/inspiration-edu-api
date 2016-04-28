# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0078_auto_20150225_1236'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='lessonstate',
            options={'ordering': ('lesson__project', 'lesson__order')},
        ),
    ]
