# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import jsonfield.fields
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0003_auto_20140810_1602'),
    ]

    operations = [
        migrations.CreateModel(
            name='TeachersFileCourseLink',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('blob', jsonfield.fields.JSONField(help_text=b'The file resource')),
                ('course', models.ForeignKey(to='api.Course')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TeachersFileLessonLink',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('blob', jsonfield.fields.JSONField(help_text=b'The file resource')),
                ('lesson', models.ForeignKey(to='api.Lesson')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
    ]
