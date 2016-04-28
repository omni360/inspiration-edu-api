# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class AlterUniqueTogetherDeferrable(migrations.AlterUniqueTogether):
    def database_forwards(self, app_label, schema_editor, from_state, to_state, backwards=False):
        old_sql_create_unique = schema_editor.sql_create_unique
        if not backwards:
            schema_editor.sql_create_unique += 'DEFERRABLE INITIALLY IMMEDIATE'
        super(AlterUniqueTogetherDeferrable, self).database_forwards(app_label, schema_editor, from_state, to_state)
        schema_editor.sql_create_unique = old_sql_create_unique

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        self.database_forwards(app_label, schema_editor, from_state, to_state, backwards=True)


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0058_auto_20141217_1526'),
    ]

    operations = [
        #remove project+order constraint, and add it again with deferrable:
        migrations.AlterUniqueTogether(
            name='lessoninproject',
            unique_together=set([('lesson', 'project')]),
        ),
        AlterUniqueTogetherDeferrable(
            name='lessoninproject',
            unique_together=set([('lesson', 'project'), ('project', 'order')]),
        ),

        #remove classroom+order constraint, and add it again with deferrable:
        migrations.AlterUniqueTogether(
            name='projectinclassroom',
            unique_together=set([('project', 'classroom')]),
        ),
        AlterUniqueTogetherDeferrable(
            name='projectinclassroom',
            unique_together=set([('project', 'classroom'), ('classroom', 'order')]),
        ),
    ]
