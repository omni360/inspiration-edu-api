# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib.auth.models import Group
from django.db import models, migrations

def add_provider_groups(apps, schema_editor):
	# create provider group for circuits
	group, created = Group.objects.get_or_create(name='circuits')
	if created:
		pass

	# create provider group for tinkercad
	group, created = Group.objects.get_or_create(name='tinkercad')
	if created:
		pass

def remove_provider_groups(apps, schema_editor):
	# remove provider group for circuits
	Group.objects.get(name='circuits').delete()
	# remove provider group for tinkercad
	Group.objects.get(name='tinkercad').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0059_auto_20141221_0959'),
    ]

    operations = [
    	migrations.RunPython(
    		add_provider_groups,
    		remove_provider_groups
    	),
    ]
