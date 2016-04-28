# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0018_auto_20140902_0832'),
    ]

    operations = [
        migrations.RenameField(
            model_name='lessonstate',
            old_name='completed_steps',
            new_name='viewed_steps',
        ),
        migrations.AlterField(
            model_name='class',
            name='materials',
            field=models.ManyToManyField(related_name=b'class_materials', to=b'api.ISBNItem'),
        ),
        migrations.AlterField(
            model_name='class',
            name='tools',
            field=models.ManyToManyField(related_name=b'class_tools', to=b'api.ISBNItem'),
        ),
        migrations.AlterField(
            model_name='course',
            name='owner',
            field=models.ForeignKey(related_name=b'authored_courses', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='igniteuser',
            name='groups',
            field=models.ManyToManyField(related_query_name='user', related_name='user_set', to=b'auth.Group', blank=True, help_text='The groups this user belongs to. A user will get all permissions granted to each of his/her group.', verbose_name='groups'),
        ),
        migrations.AlterField(
            model_name='igniteuser',
            name='user_permissions',
            field=models.ManyToManyField(related_query_name='user', related_name='user_set', to=b'auth.Permission', blank=True, help_text='Specific permissions for this user.', verbose_name='user permissions'),
        ),
        migrations.AlterField(
            model_name='instruction',
            name='step',
            field=models.ForeignKey(related_name=b'instructions', to='api.Step'),
        ),
        migrations.AlterField(
            model_name='lesson',
            name='classes',
            field=models.ManyToManyField(related_name=b'lessons', through='api.LessonInClass', to=b'api.Class'),
        ),
        migrations.AlterField(
            model_name='lesson',
            name='courses',
            field=models.ManyToManyField(related_name=b'lessons', through='api.LessonInCourse', to=b'api.Course'),
        ),
        migrations.AlterField(
            model_name='lesson',
            name='owner',
            field=models.ForeignKey(related_name=b'authored_lessons', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='picturecourselink',
            name='course',
            field=models.ForeignKey(related_name=b'pictures', to='api.Course'),
        ),
        migrations.AlterField(
            model_name='step',
            name='lesson',
            field=models.ForeignKey(related_name=b'steps', to='api.Lesson'),
        ),
        migrations.AlterField(
            model_name='teachersfilecourselink',
            name='course',
            field=models.ForeignKey(related_name=b'teachers_files', to='api.Course'),
        ),
        migrations.AlterField(
            model_name='teachersfilelessonlink',
            name='lesson',
            field=models.ForeignKey(related_name=b'teachers_files', to='api.Lesson'),
        ),
        migrations.AlterField(
            model_name='videocourselink',
            name='course',
            field=models.ForeignKey(related_name=b'videos', to='api.Course'),
        ),
    ]
