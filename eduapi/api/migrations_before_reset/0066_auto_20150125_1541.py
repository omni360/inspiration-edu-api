# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.db.models import Count


def set_initial_completed_projects(apps, schema_editor):
    ProjectState = apps.get_model('api', 'ProjectState')
    LessonState = apps.get_model('api', 'LessonState')

    project_states = ProjectState.objects \
        .annotate(lessons_count=Count('project__lessons')) \
        .all()

    for ps in project_states:
        ps.is_completed = LessonState.objects.filter(
            user=ps.user,
            lesson__projects=ps.project,
            is_completed=True,
        ).count() == ps.lessons_count

        # Save only if ProjectState is True. Otherwise,
        # there was no change in the PS and thus there's
        # no need to save.
        if ps.is_completed:
            ps.save()

def noop(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('api', '0065_auto_20150125_1443'),
    ]

    operations = [
        migrations.RunPython(
            set_initial_completed_projects,
            noop,
        ),
    ]
