# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0054_auto_20141208_1157'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='lessonstate',
            unique_together=set([('user', 'lesson')]),
        ),
    ]
