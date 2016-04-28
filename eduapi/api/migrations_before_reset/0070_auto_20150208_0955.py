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
        ('api', '0069_auto_20150202_0944'),
    ]

    operations = [
        migrations.AddField(
            model_name='lesson',
            name='order',
            field=models.IntegerField(default=None, null=True, db_index=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='lesson',
            name='project',
            field=models.ForeignKey(related_name='lessons', to='api.Project', null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='lesson',
            name='projects',
            field=models.ManyToManyField(related_name='lessons_old', through='api.LessonInProject', to='api.Project'),
            preserve_default=True,
        ),
        #custom migration - define (project, order) constraint as DEFERRABLE
        AlterUniqueTogetherDeferrable(
            name='lesson',
            unique_together=set([('project', 'order')]),
        ),
        migrations.RemoveField(
            model_name='lesson',
            name='is_published',
        ),
        migrations.AlterModelOptions(
            name='lesson',
            options={'ordering': ('project', 'order')},
        ),
    ]
