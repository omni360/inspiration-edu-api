# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0027_auto_20140918_1137'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lessoninclassroom',
            name='classroom',
            field=models.ForeignKey(related_name=b'lessons_through_set', to='api.Classroom'),
        ),
        migrations.AlterField(
            model_name='lessonincourse',
            name='course',
            field=models.ForeignKey(related_name=b'lessons_through_set', to='api.Course'),
        ),
    ]
