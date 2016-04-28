# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0046_auto_20141119_1502'),
    ]

    operations = [
        migrations.CreateModel(
            name='CourseInClassroom',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('order', models.IntegerField(default=0, help_text=b'The order in which the course should be taken in the classroom', db_index=True)),
                ('classroom', models.ForeignKey(related_name='courses_through_set', to='api.Classroom')),
                ('course', models.ForeignKey(to='api.Course')),
            ],
            options={
                'ordering': ['classroom', 'order'],
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='lessoninclassroom',
            unique_together=None,
        ),
        migrations.RemoveField(
            model_name='lessoninclassroom',
            name='classroom',
        ),
        migrations.RemoveField(
            model_name='lessoninclassroom',
            name='lesson',
        ),
        migrations.RemoveField(
            model_name='pictureclassroomlink',
            name='classroom',
        ),
        migrations.DeleteModel(
            name='PictureClassroomLink',
        ),
        migrations.RemoveField(
            model_name='teachersfileclassroomlink',
            name='classroom',
        ),
        migrations.DeleteModel(
            name='TeachersFileClassroomLink',
        ),
        migrations.RemoveField(
            model_name='videoclassroomlink',
            name='classroom',
        ),
        migrations.DeleteModel(
            name='VideoClassroomLink',
        ),
        migrations.AlterUniqueTogether(
            name='courseinclassroom',
            unique_together=set([('course', 'classroom', 'order')]),
        ),
        migrations.RemoveField(
            model_name='classroom',
            name='age',
        ),
        migrations.RemoveField(
            model_name='classroom',
            name='base_course',
        ),
        migrations.RemoveField(
            model_name='classroom',
            name='difficulty',
        ),
        migrations.RemoveField(
            model_name='classroom',
            name='duration',
        ),
        migrations.RemoveField(
            model_name='classroom',
            name='is_published',
        ),
        migrations.RemoveField(
            model_name='classroom',
            name='license',
        ),
        migrations.RemoveField(
            model_name='classroom',
            name='materials_additional',
        ),
        migrations.RemoveField(
            model_name='classroom',
            name='materials_for_sale',
        ),
        migrations.RemoveField(
            model_name='classroom',
            name='teacher_info',
        ),
        migrations.RemoveField(
            model_name='classroom',
            name='tools_additional',
        ),
        migrations.RemoveField(
            model_name='classroom',
            name='tools_for_sale',
        ),
        migrations.RemoveField(
            model_name='lesson',
            name='classrooms',
        ),
        migrations.DeleteModel(
            name='LessonInClassroom',
        ),
        migrations.AddField(
            model_name='course',
            name='classrooms',
            field=models.ManyToManyField(related_name='courses', through='api.CourseInClassroom', to='api.Classroom'),
            preserve_default=True,
        ),
    ]
