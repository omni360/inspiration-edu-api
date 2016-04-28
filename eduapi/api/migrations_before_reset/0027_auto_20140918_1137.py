# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.utils.timezone
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0026_auto_20140918_1131'),
    ]

    operations = [
        migrations.CreateModel(
            name='Classroom',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('is_published', models.BooleanField(default=False)),
                ('title', models.CharField(help_text=b"Course's title as it will be displayed to students", max_length=120)),
                ('description', models.TextField(default=b'', help_text=b"A short description of the course's goals and characteristics", blank=True)),
                ('banner_image', models.URLField(help_text=b'A URL of a cover picture for the course', null=True, blank=True)),
                ('card_image', models.URLField(help_text=b'A URL of a card picture for the course', null=True, blank=True)),
                ('duration', models.PositiveIntegerField(default=0, help_text=b'The expected duration of the lesson in minutes')),
                ('age', models.CharField(default=b'3+', help_text=b'The required age', max_length=10, choices=[(b'3+', b'3+'), (b'6+', b'6+'), (b'9+', b'9+'), (b'12+', b'12+'), (b'15+', b'15+'), (b'18+', b'18+')])),
                ('difficulty', models.CharField(default=b'easy', help_text=b'Difficulty level', max_length=15, choices=[(b'easy', b'Easy'), (b'intermediate', b'Intermediate'), (b'hard', b'Hard')])),
                ('teacher_info', models.TextField(default=b'', help_text=b'Information about the teacher who published the lesson', blank=True)),
                ('license', models.CharField(default=b'Public Domain', help_text=b'The license that this course operates under', max_length=30, choices=[(b'CC-BY 3.0', b'CC: Attribution 3.0 Unported'), (b'CC-BY-NC 3.0', b'CC: Attribution-NonCommercial 3.0 Unported'), (b'CC-BY-SA 3.0', b'CC: Attribution-ShareAlike 3.0 Unported'), (b'CC-BY-NC-SA 3.0', b'CC: Attribution-NonCommercial-ShareAlike 3.0 Unported'), (b'Public Domain', b'Public Domain')])),
                ('materials_additional', models.ManyToManyField(to='api.Material')),
                ('materials_for_sale', models.ManyToManyField(to='api.MaterialForSale')),
                ('owner', models.ForeignKey(related_name=b'authored_classroooms', to=settings.AUTH_USER_MODEL)),
                ('tools_additional', models.ManyToManyField(to='api.Tool')),
                ('tools_for_sale', models.ManyToManyField(to='api.ToolForSale')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='LessonInClassroom',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('order', models.IntegerField(default=0, help_text=b'The order in which the lesson should be taken in the classroom')),
                ('classroom', models.ForeignKey(to='api.Classroom')),
                ('lesson', models.ForeignKey(to='api.Lesson')),
            ],
            options={
                'ordering': ['classroom', 'order'],
            },
            bases=(models.Model,),
        ),
        migrations.RemoveField(
            model_name='class',
            name='materials_additional',
        ),
        migrations.RemoveField(
            model_name='class',
            name='materials_for_sale',
        ),
        migrations.RemoveField(
            model_name='class',
            name='owner',
        ),
        migrations.RemoveField(
            model_name='class',
            name='tools_additional',
        ),
        migrations.RemoveField(
            model_name='class',
            name='tools_for_sale',
        ),
        migrations.AlterUniqueTogether(
            name='lessoninclass',
            unique_together=None,
        ),
        migrations.RemoveField(
            model_name='lessoninclass',
            name='class_obj',
        ),
        migrations.RemoveField(
            model_name='lessoninclass',
            name='lesson',
        ),
        migrations.AlterUniqueTogether(
            name='lessoninclassroom',
            unique_together=set([('lesson', 'classroom', 'order')]),
        ),
        migrations.RemoveField(
            model_name='lesson',
            name='classes',
        ),
        migrations.DeleteModel(
            name='LessonInClass',
        ),
        migrations.DeleteModel(
            name='Class',
        ),
        migrations.AddField(
            model_name='lesson',
            name='classrooms',
            field=models.ManyToManyField(related_name=b'lessons', through='api.LessonInClassroom', to='api.Classroom'),
            preserve_default=True,
        ),
    ]
