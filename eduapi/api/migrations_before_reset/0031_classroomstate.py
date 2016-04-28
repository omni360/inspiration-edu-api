# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.utils.timezone
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0030_pictureclassroomlink_teachersfileclassroomlink_videoclassroomlink'),
    ]

    operations = [
        migrations.CreateModel(
            name='ClassroomState',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('classroom', models.ForeignKey(related_name=b'registrations', to='api.Classroom')),
                ('lessons', models.ManyToManyField(to='api.LessonState')),
                ('user', models.ForeignKey(related_name=b'classrooms', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
    ]
