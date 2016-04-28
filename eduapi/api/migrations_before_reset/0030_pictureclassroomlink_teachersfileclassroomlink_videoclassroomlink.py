# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import jsonfield.fields
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0029_delete_isbnitem'),
    ]

    operations = [
        migrations.CreateModel(
            name='PictureClassroomLink',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('url', models.CharField(help_text=b'The url of the picture.', max_length=512)),
                ('classroom', models.ForeignKey(related_name=b'pictures', to='api.Classroom')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TeachersFileClassroomLink',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('blob', jsonfield.fields.JSONField(help_text=b'The file resource')),
                ('classroom', models.ForeignKey(related_name=b'teachers_files', to='api.Classroom')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='VideoClassroomLink',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('blob', jsonfield.fields.JSONField(help_text=b'The video resource')),
                ('classroom', models.ForeignKey(related_name=b'videos', to='api.Classroom')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
    ]
