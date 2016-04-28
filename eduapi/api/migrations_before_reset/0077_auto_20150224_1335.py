# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0076_auto_20150224_1332'),
    ]

    lessonstate_table = 'api_lessonstate'
    projectstate_table = 'api_projectstate'
    lesson_table = 'api_lesson'
    project_table = 'api_project'

    operations = [
        migrations.RunSQL(
            sql=(
                    'UPDATE "%(lessonstate_table)s" "U0" SET "project_state_id" = ('
                    'SELECT  "U3"."id"'
                    ' FROM "%(lesson_table)s" "U1" INNER JOIN "%(project_table)s" "U2" ON ("U2"."id"="U1"."project_id") INNER JOIN "%(projectstate_table)s" "U3" ON ("U3"."project_id"="U2"."id")'
                    ' WHERE "U0"."lesson_id"="U1"."id" AND "U0"."user_id"="U3"."user_id"'
                    ')'
                ) % {
                    'lessonstate_table': lessonstate_table,
                    'projectstate_table': projectstate_table,
                    'lesson_table': lesson_table,
                    'project_table': project_table,
                },
            reverse_sql=(
                    'UPDATE "%(lessonstate_table)s" "U0" SET"user_id" = ('
                    'SELECT  "U3"."user_id"'
                    ' FROM "%(lesson_table)s" "U1" INNER JOIN "%(project_table)s" "U2" ON ("U2"."id"="U1"."project_id") INNER JOIN "%(projectstate_table)s" "U3" ON ("U3"."project_id"="U2"."id")'
                    ' WHERE "U0"."lesson_id"="U1"."id" AND "U0"."project_state_id"="U3"."id"'
                    ')'
                ) % {
                    'lessonstate_table': lessonstate_table,
                    'projectstate_table': projectstate_table,
                    'lesson_table': lesson_table,
                    'project_table': project_table,
                }
        )
    ]
