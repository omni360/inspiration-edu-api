# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.utils.timezone

from django.db.migrations.operations.base import Operation


# Make custom migrations to only fix model state changes, since the database is already migrated (at 0054):
# Django had problems with renaming models that are used as through models.
class FixThroughModelsStateChange(Operation):
    def state_forwards(self, app_label, state):
        through_models_state_changes = {
            'CourseState': {
                'new_name': 'ProjectState',
                'dependencies': {
                    'ClassroomState': {'projects': 'to',},
                },
            },
            'LessonInCourse': {
                'new_name': 'LessonInProject',
                'dependencies': {
                    'Lesson': {'projects': 'through',},
                },
            },
            'CourseInClassroom': {
                'new_name': 'ProjectInClassroom',
                'dependencies': {
                    'Project': {'classrooms': 'through',},
                },
            },
        }

        for through_model_name, through_model_state_changes in through_models_state_changes.iteritems():
            # print 'Rename model', through_model_name
            #rename through model:
            state.models[app_label, through_model_state_changes['new_name'].lower()] = state.models[app_label, through_model_name.lower()]
            state.models[app_label, through_model_state_changes['new_name'].lower()].name = through_model_state_changes['new_name']
            del state.models[app_label, through_model_name.lower()]

            #change dependencies fields:
            for through_model_dep_name, through_model_dep_fields_changes in through_model_state_changes['dependencies'].iteritems():
                through_model_dep = state.models[app_label, through_model_dep_name.lower()]
                through_model_dep_new_fields = []
                for through_model_dep_field_name, through_model_dep_field in through_model_dep.fields:
                    if through_model_dep_field_name in through_model_dep_fields_changes:
                        # print 'Change relation %s.%s' % (through_model_dep_name, through_model_dep_field_name)
                        through_model_dep_field = through_model_dep_field.clone()
                        setattr(through_model_dep_field.rel, through_model_dep_fields_changes[through_model_dep_field_name], '%s.%s' % (app_label, through_model_state_changes['new_name']))
                    through_model_dep_new_fields.append((through_model_dep_field_name, through_model_dep_field))
                through_model_dep.fields = through_model_dep_new_fields

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        pass
    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        pass
    def describe(self):
        return 'Fix to change through models state'


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0055_auto_20141209_1624'),
    ]

    operations = [
        FixThroughModelsStateChange(),
    ]
