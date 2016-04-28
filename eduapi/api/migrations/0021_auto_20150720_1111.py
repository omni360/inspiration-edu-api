# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


def migrate_publish_mode_forwards(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    Project = apps.get_model('api', 'Project')

    # Change publish_mode according to is_published:
    Project.objects.using(db_alias).filter(is_published=False).update(publish_mode='edit')
    Project.objects.using(db_alias).filter(is_published=True).update(publish_mode='published')

def migrate_publish_mode_backwards(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    Project = apps.get_model('api', 'Project')

    # Change is_published according to publish_mode:
    Project.objects.using(db_alias).exclude(publish_mode='published').update(is_published=False)
    Project.objects.using(db_alias).filter(publish_mode='published').update(is_published=True)


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0020_auto_20150720_1111'),
    ]

    operations = [
        migrations.RunPython(
            code=migrate_publish_mode_forwards,
            reverse_code=migrate_publish_mode_backwards
        )
    ]
