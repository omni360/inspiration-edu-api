# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0023_auto_20140904_1751'),
    ]

    operations = [
        migrations.AlterField(
            model_name='coursestate',
            name='user',
            field=models.ForeignKey(related_name=b'courses', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='lessonstate',
            name='user',
            field=models.ForeignKey(related_name=b'lessons', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='review',
            name='rating',
            field=models.IntegerField(choices=[(1, 1), (2, 2), (3, 3), (4, 4), (5, 5), (6, 6), (7, 7), (8, 8), (9, 9), (10, 10)]),
        ),
    ]
