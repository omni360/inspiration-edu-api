# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings

def map_homepage_group_to_id_one(apps, schema_editor):
    ProjectGroup = apps.get_model('api', 'ProjectGroup')
    try:
        pg_one = ProjectGroup.objects.get(id=1)
        if pg_one.group_name != 'homegroup':
            try:
                pg_homegroup = ProjectGroup.objects.get(group_name='homegroup')
                pg_homegroup.group_name = 'homegroup_alt'
                pg_homegroup.save()
                pg_one.projects = pg_homegroup.projects
            except ProjectGroup.DoesNotExist:
                if not pg_one.projects:
                    pg_one.projects = settings.HOMEPAGE_PROJECTS_IDS
                pg_one.group_name = 'homegroup'
                pg_one.save()
    except ProjectGroup.DoesNotExist:
        try:
            pg_homegroup = ProjectGroup.objects.get(group_name='homegroup')
            if pg_homegroup.id != 1:
                pg_homegroup.group_name = 'homegroup_alt'
                pg_homegroup.save()
                pg = ProjectGroup(id=1, group_name='homegroup', projects=settings.HOMEPAGE_PROJECTS_IDS)
                ProjectGroup.objects.bulk_create([pg,])
        except ProjectGroup.DoesNotExist:
            pg = ProjectGroup(id=1, group_name='homegroup', projects=settings.HOMEPAGE_PROJECTS_IDS)
            ProjectGroup.objects.bulk_create([pg,])

def erase_homepage_group(apps, schema_editor):
    ProjectGroup = apps.get_model('api', 'ProjectGroup')
    try:
        pg_one = ProjectGroup.objects.get(id=1)
        pg_one.delete()
        pg_homegroup = ProjectGroup.objects.get(group_name='homegroup')
        pg_homegroup.delete()
    except ProjectGroup.DoesNotExist:
        try:
            pg_homegroup = ProjectGroup.objects.get(group_name='homegroup')
            pg_homegroup.delete()
        except:
            pass

class Migration(migrations.Migration):

    dependencies = [
        ('api', '0026_auto_20150812_1015'),
    ]

    operations = [
        migrations.RunPython(map_homepage_group_to_id_one,
                             erase_homepage_group)
    ]
