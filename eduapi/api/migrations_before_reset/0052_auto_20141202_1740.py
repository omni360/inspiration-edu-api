# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


def delete_duplicates(model, unique_fields):
    #get list of all model unique fields and counter of duplicates:
    count_info = model.objects.values(*unique_fields).annotate(dups=models.Count('id', distinct=False))
    dups_info = count_info.values(*unique_fields).filter(dups__gt=1)

    #for each duplicated model unique fields, keep the first item and delete the rest:
    for dup_info in dups_info:
        dup_items = model.objects.filter(**dup_info)
        dup_item_to_keep = dup_items.first()
        dup_items_to_delete = dup_items.exclude(pk=dup_item_to_keep.pk)
        dup_items_to_delete.delete()

def forwards_func(apps, schema_editor):
    '''
    Delete duplicate unique keys.
    No backward migration.
    '''
    delete_duplicates(apps.get_model("api", 'LessonState'),         ('user', 'lesson'))


def backwards_func(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0051_auto_20141202_1731'),
    ]

    operations = [
        migrations.RunPython(
            forwards_func,
            backwards_func
        ),
    ]
