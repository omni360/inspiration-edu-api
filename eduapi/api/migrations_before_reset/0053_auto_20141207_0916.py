# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0052_auto_20141202_1740'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='lessonincourse',
            options={'ordering': ['project', 'order']},
        ),
        migrations.RenameField(
            model_name='classroomstate',
            old_name='courses',
            new_name='projects',
        ),
        migrations.RenameField(
            model_name='courseinclassroom',
            old_name='course',
            new_name='project',
        ),
        migrations.RenameField(
            model_name='coursestate',
            old_name='course',
            new_name='project',
        ),
        migrations.RenameField(
            model_name='lesson',
            old_name='courses',
            new_name='projects',
        ),
        migrations.RenameField(
            model_name='lessonincourse',
            old_name='course',
            new_name='project',
        ),
        migrations.RenameField(
            model_name='picturecourselink',
            old_name='course',
            new_name='project',
        ),
        migrations.RenameField(
            model_name='teachersfilecourselink',
            old_name='course',
            new_name='project',
        ),
        migrations.RenameField(
            model_name='videocourselink',
            old_name='course',
            new_name='project',
        ),
        migrations.AlterField(
            model_name='classroom',
            name='banner_image',
            field=models.URLField(help_text=b'A URL of a cover picture for the classroom', null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='classroom',
            name='card_image',
            field=models.URLField(help_text=b'A URL of a card picture for the classroom', null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='classroom',
            name='description',
            field=models.TextField(default=b'', help_text=b"A short description of the classroom's goals and characteristics", blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='classroom',
            name='title',
            field=models.CharField(help_text=b"Classroom's title as it will be displayed to students", max_length=120),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='course',
            name='banner_image',
            field=models.URLField(help_text=b'A URL of a cover picture for the project', null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='course',
            name='card_image',
            field=models.URLField(help_text=b'A URL of a card picture for the project', null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='course',
            name='classrooms',
            field=models.ManyToManyField(related_name='projects', through='api.CourseInClassroom', to='api.Classroom'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='course',
            name='description',
            field=models.TextField(default=b'', help_text=b"A short description of the project's goals and characteristics", blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='course',
            name='license',
            field=models.CharField(default=b'Public Domain', help_text=b'The license that this project operates under', max_length=30, choices=[(b'CC-BY 3.0', b'CC: Attribution 3.0 Unported'), (b'CC-BY-NC 3.0', b'CC: Attribution-NonCommercial 3.0 Unported'), (b'CC-BY-SA 3.0', b'CC: Attribution-ShareAlike 3.0 Unported'), (b'CC-BY-NC-SA 3.0', b'CC: Attribution-NonCommercial-ShareAlike 3.0 Unported'), (b'Public Domain', b'Public Domain')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='course',
            name='owner',
            field=models.ForeignKey(related_name='authored_projects', to=settings.AUTH_USER_MODEL),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='course',
            name='title',
            field=models.CharField(help_text=b"Project's title as it will be displayed to students", max_length=120),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='courseinclassroom',
            name='classroom',
            field=models.ForeignKey(related_name='projects_through_set', to='api.Classroom'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='courseinclassroom',
            name='order',
            field=models.IntegerField(default=0, help_text=b'The order in which the project should be taken in the classroom', db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='coursestate',
            name='user',
            field=models.ForeignKey(related_name='projects', to=settings.AUTH_USER_MODEL),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='lesson',
            name='license',
            field=models.CharField(default=b'Public Domain', help_text=b'The license that this lesson operates under', max_length=30, choices=[(b'CC-BY 3.0', b'CC: Attribution 3.0 Unported'), (b'CC-BY-NC 3.0', b'CC: Attribution-NonCommercial 3.0 Unported'), (b'CC-BY-SA 3.0', b'CC: Attribution-ShareAlike 3.0 Unported'), (b'CC-BY-NC-SA 3.0', b'CC: Attribution-NonCommercial-ShareAlike 3.0 Unported'), (b'Public Domain', b'Public Domain')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='lessonincourse',
            name='order',
            field=models.IntegerField(default=0, help_text=b'The order in which the lesson should be taken in the project', db_index=True),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='courseinclassroom',
            unique_together=set([('project', 'classroom'), ('classroom', 'order')]),
        ),
        migrations.AlterUniqueTogether(
            name='coursestate',
            unique_together=set([('user', 'project')]),
        ),
        migrations.AlterUniqueTogether(
            name='lessonincourse',
            unique_together=set([('lesson', 'project'), ('project', 'order')]),
        ),
    ]
