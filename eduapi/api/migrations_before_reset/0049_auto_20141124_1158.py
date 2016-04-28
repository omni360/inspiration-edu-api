# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


def delete_all_classrooms(apps, schema_editor):
    '''Delete all of the classroom objects from the DB'''
    
    # We get the model from the versioned app registry;
    # if we directly import it, it'll be the wrong version
    Classroom = apps.get_model("api", "Classroom")
    db_alias = schema_editor.connection.alias

    # Delete all classrooms.
    Classroom.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0048_auto_20141124_0019'),
    ]

    operations = [
        migrations.RunPython(
            delete_all_classrooms,
            reverse_code=delete_all_classrooms,
        ),
    ]
