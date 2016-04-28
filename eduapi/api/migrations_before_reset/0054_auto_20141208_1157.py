# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import jsonfield.fields
import django.utils.timezone
from django.conf import settings
import api.models.fields


models_through_tables_renamings = {
    'Course':[
        ('api_course_materials_additional',     'api_project_materials_additional'),
        ('api_course_materials_for_sale',       'api_project_materials_for_sale'),
        ('api_course_tools_additional',         'api_project_tools_additional'),
        ('api_course_tools_for_sale',           'api_project_tools_for_sale'),
    ],

    'CourseState':[
        ('api_coursestate',         'api_projectstate'),
        ('api_coursestate_lessons', 'api_projectstate_lessons'),
    ],

    'LessonInCourse': [
        ('api_lessonincourse',      'api_lessoninproject'),
    ],
    'CourseInClassroom':[
        ('api_courseinclassroom',   'api_projectinclassroom'),
    ],
}
through_tables_columns_renamings = {
    'api_classroomstate_projects': [
        ('coursestate_id',      'projectstate_id'),
    ],

    'api_projectstate_lessons': [
        ('coursestate_id',      'projectstate_id'),
    ],

    'api_project_materials_additional': [
        ('course_id',           'project_id'),
    ],
    'api_project_materials_for_sale': [
        ('course_id',           'project_id'),
    ],
    'api_project_tools_additional': [
        ('course_id',           'project_id'),
    ],
    'api_project_tools_for_sale': [
        ('course_id',           'project_id'),
    ],
}


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0053_auto_20141207_0916'),
    ]


    def forwards_through_tables(self, schema_editor):
        for model_with_through, through_table_renamings in models_through_tables_renamings.iteritems():
            for through_table_old, through_table_new in through_table_renamings:
                # print 'Through table migration:', model_with_through, through_table_old, through_table_new
                schema_editor.alter_db_table(model_with_through, through_table_old, through_table_new)
        for through_table_name, through_table_columns_renamings in through_tables_columns_renamings.iteritems():
            for through_table_column_old, through_table_column_new in through_table_columns_renamings:
                # print 'Through table column migration:', through_table_name, through_table_column_old, through_table_column_new
                schema_editor.execute(schema_editor.sql_rename_column % {
                    'table': through_table_name,
                    'old_column': through_table_column_old,
                    'new_column': through_table_column_new
                })

    def backwards_through_tables(self, schema_editor):
        for model_with_through, through_table_renamings in models_through_tables_renamings.iteritems():
            for through_table_old, through_table_new in through_table_renamings:
                schema_editor.alter_db_table(model_with_through, through_table_new, through_table_old)
        for through_table_name, through_table_columns_renamings in through_tables_columns_renamings.iteritems():
            for through_table_column_old, through_table_column_new in through_table_columns_renamings:
                schema_editor.execute(schema_editor.sql_rename_column % {
                    'table': through_table_name,
                    'old_column': through_table_column_new,
                    'new_column': through_table_column_old
                })


    operations = [
        migrations.RenameModel(
            old_name='Course',
            new_name='Project',
        ),

        migrations.RenameModel(
            old_name='TeachersFileCourseLink',
            new_name='TeachersFileProjectLink',
        ),
        migrations.RenameModel(
            old_name='VideoCourseLink',
            new_name='VideoProjectLink',
        ),
        migrations.RenameModel(
            old_name='PictureCourseLink',
            new_name='PictureProjectLink',
        ),

        # This makes problem with coursestate_id in api_coursestate_lessons through table. Handled manually below.
        # migrations.RenameModel(
        #     old_name='CourseState',
        #     new_name='ProjectState',
        # ),

        # run python to rename through tables:
        migrations.RunPython(
            forwards_through_tables,
            backwards_through_tables
        ),
    ]
