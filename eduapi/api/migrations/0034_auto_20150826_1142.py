# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

import re


class AlterUniquePartialIndexTogether(migrations.AlterIndexTogether):
    def __init__(self, name, index_together, ):
        super(AlterUniquePartialIndexTogether, self).__init__(name, index_together)

    def database_forwards(self, app_label, schema_editor, from_state, to_state, backwards=False):
        old_sql_create_index = schema_editor.sql_create_index
        if not backwards:
            schema_editor.sql_create_index = schema_editor.sql_create_index.replace('CREATE INDEX', 'CREATE UNIQUE INDEX', 1)
            # schema_editor.sql_create_index += ' DEFERRABLE INITIALLY IMMEDIATE'  #create unique index does not support deferrable
            schema_editor.sql_create_index = schema_editor.sql_create_index + ' WHERE "is_deleted"=FALSE'
        super(AlterUniquePartialIndexTogether, self).database_forwards(app_label, schema_editor, from_state, to_state)
        schema_editor.sql_create_index = old_sql_create_index

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        self.database_forwards(app_label, schema_editor, from_state, to_state, backwards=True)


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0033_auto_20150825_1512'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='lesson',
            unique_together=set([]),
        ),
        migrations.AlterUniqueTogether(
            name='step',
            unique_together=set([]),
        ),
        AlterUniquePartialIndexTogether(
            name='lesson',
            index_together=set([('project', 'order')]),
        ),
        AlterUniquePartialIndexTogether(
            name='step',
            index_together=set([('lesson', 'order')]),
        ),
    ]
