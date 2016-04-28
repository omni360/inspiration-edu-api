# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.db.models import Count


def set_initial_completed_lessons(apps, schema_editor):
    
    LessonState = apps.get_model('api', 'LessonState')

    # Get all of the lesson states with the number of 
    # steps that the lesson has and the number of completed steps.
    lesson_states = LessonState.objects \
        .annotate(
            step_count=Count('lesson__steps'),
            completed_steps_count=Count('stepstate'),
        )

    # Mark all of the lessons with an equal number of completed and total steps
    # as completed. Note that lessons with 0 steps also count.
    for ls in lesson_states:
        if ls.step_count == ls.completed_steps_count:
            ls.is_completed = True
            ls.save()


def noop(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('api', '0064_merge'),
    ]

    operations = [
        migrations.RunPython(
            set_initial_completed_lessons,
            noop,
        ),
    ]
