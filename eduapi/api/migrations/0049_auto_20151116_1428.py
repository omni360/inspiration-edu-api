# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0048_merge'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='classroominvite',
            name='classroom',
        ),
        migrations.RemoveField(
            model_name='classroominvite',
            name='invitee',
        ),
        migrations.RemoveField(
            model_name='instruction',
            name='step',
        ),
        migrations.RemoveField(
            model_name='pictureprojectlink',
            name='project',
        ),
        migrations.RemoveField(
            model_name='videoprojectlink',
            name='project',
        ),
        migrations.RemoveField(
            model_name='lesson',
            name='description',
        ),
        migrations.RemoveField(
            model_name='lesson',
            name='image',
        ),
        migrations.RemoveField(
            model_name='lesson',
            name='teachers_files_list',
        ),
        migrations.RemoveField(
            model_name='project',
            name='materials_additional',
        ),
        migrations.RemoveField(
            model_name='project',
            name='materials_for_sale',
        ),
        migrations.RemoveField(
            model_name='project',
            name='picture_links_list',
        ),
        migrations.RemoveField(
            model_name='project',
            name='tools_additional',
        ),
        migrations.RemoveField(
            model_name='project',
            name='tools_for_sale',
        ),
        migrations.RemoveField(
            model_name='project',
            name='video_links_list',
        ),
        migrations.RemoveField(
            model_name='step',
            name='instructions_count',
        ),
        migrations.DeleteModel(
            name='ClassroomInvite',
        ),
        migrations.DeleteModel(
            name='Instruction',
        ),
        migrations.DeleteModel(
            name='Material',
        ),
        migrations.DeleteModel(
            name='MaterialForSale',
        ),
        migrations.DeleteModel(
            name='PictureProjectLink',
        ),
        migrations.DeleteModel(
            name='Tool',
        ),
        migrations.DeleteModel(
            name='ToolForSale',
        ),
        migrations.DeleteModel(
            name='VideoProjectLink',
        ),
    ]
