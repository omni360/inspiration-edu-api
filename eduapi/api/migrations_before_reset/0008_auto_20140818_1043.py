# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.utils.timezone
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('api', '0007_auto_20140816_1440'),
    ]

    operations = [
        migrations.CreateModel(
            name='CourseState',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('course', models.ForeignKey(to='api.Course')),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='LessonState',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('application_id', models.CharField(max_length=50, blank=True)),
                ('active', models.BooleanField(default=False)),
                ('joinURL', models.CharField(max_length=1024, blank=True)),
                ('lesson', models.ForeignKey(to='api.Lesson')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='coursestate',
            name='lessons',
            field=models.ManyToManyField(to='api.LessonState'),
            preserve_default=True,
        ),
        migrations.CreateModel(
            name='StepState',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('state', models.CharField(max_length=50, blank=True)),
                ('step', models.ForeignKey(to='api.Step')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='lessonstate',
            name='steps',
            field=models.ManyToManyField(to='api.StepState'),
            preserve_default=True,
        ),
        migrations.AlterModelOptions(
            name='igniteuser',
            options={},
        ),
    ]
