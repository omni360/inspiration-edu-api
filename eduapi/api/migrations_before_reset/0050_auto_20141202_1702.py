# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


def forwards_func(apps, schema_editor):
    '''
    Delete duplicate step states.
    No backward migration.
    '''
    StepState = apps.get_model("api", "StepState")
    db_alias = schema_editor.connection.alias

    #get list of all step states and counter of duplicates:
    count_steptates_info = StepState.objects.values('step', 'lesson_state').annotate(dups=models.Count('id', distinct=False))
    dups_stepstates_info = count_steptates_info.values('step', 'lesson_state').filter(dups__gt=1)

    #for each duplicated step state, keep the first item and delete the rest:
    for dup_stepstate_info in dups_stepstates_info:
        dup_stepstate_items = StepState.objects.filter(**dup_stepstate_info)
        dup_stepstate_item_to_keep = dup_stepstate_items.first()
        dup_stepstate_items_to_delete = dup_stepstate_items.exclude(pk=dup_stepstate_item_to_keep.pk)
        dup_stepstate_items_to_delete.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0049_auto_20141124_1158'),
    ]

    operations = [
        migrations.RunPython(
            forwards_func
        ),
        migrations.AlterUniqueTogether(
            name='stepstate',
            unique_together=set([('step', 'lesson_state')]),
        ),
    ]
