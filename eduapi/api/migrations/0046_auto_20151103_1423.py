# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import ast

from django.db import models, migrations


def turn_hints_to_instructions(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    Step = apps.get_model('api', 'Step')
    steps = Step.objects.using(db_alias).exclude(hint='')

    for step in steps:
        step = Step.objects.get(id=step.id)
        if step.instructions_list and len(step.instructions_list) > 0:
            step.instructions_list = [ast.literal_eval(instruction) for instruction in step.instructions_list]
            step.instructions_list.append({'description': 'Stuck?', 'hint': step.hint})
            step.save()
        else:
            step.instructions_list = [{'description': step.hint}]

def return_do_hints_from_steps(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    Step = apps.get_model('api', 'Step')
    steps = Step.objects.using(db_alias).filter(title='Stuck?')
    for step in steps:
        prev_step = Step.objects.using(db_alias).filter(lesson=step.lesson, order=step.order-1)[0]
        prev_step.hint = step.description
        prev_step.save()

    steps.delete()

class Migration(migrations.Migration):

    dependencies = [
        ('api', '0045_auto_20151102_1426'),
    ]

    operations = [
        migrations.RunPython(turn_hints_to_instructions, return_do_hints_from_steps),
    ]
