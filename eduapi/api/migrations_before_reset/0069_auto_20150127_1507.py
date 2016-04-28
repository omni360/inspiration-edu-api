# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


def fix_groups_names(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')

    circuits = Group.objects.get(name='circuits')
    circuits.name = '123dcircuits'
    circuits.save()
    

def unfix_groups_names(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')

    circuits = Group.objects.get(name='123dcircuits')
    circuits.name = 'circuits'
    circuits.save()


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0068_auto_20150127_1218'),
    ]

    operations = [
        
        migrations.RunPython(
            fix_groups_names,
            unfix_groups_names,
        ),
    ]
