# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0019_auto_20140904_1120'),
    ]

    operations = [
        migrations.AlterField(
            model_name='coursestate',
            name='course',
            field=models.ForeignKey(related_name=b'registrations', to='api.Course'),
        ),
        migrations.AlterField(
            model_name='lessonstate',
            name='lesson',
            field=models.ForeignKey(related_name=b'registrations', to='api.Lesson'),
        ),
    ]
