# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0060_childguardian'),
    ]

    old_table = 'api_igniteuser_guardians'
    new_table = 'api_childguardian'

    operations = [
        # Data Migration: Copy all entries from old table to new table:
        migrations.RunSQL(
            sql=(
                    'INSERT INTO "%(new_table)s" ("child_id", "guardian_id", "moderator_type", "added", "updated")'
                    ' SELECT "%(old_table)s"."from_igniteuser_id", "%(old_table)s"."to_igniteuser_id", \'parent\', NOW(), NOW() FROM "%(old_table)s"'
                ) % {
                    'old_table': old_table,
                    'new_table': new_table,
                },
            reverse_sql=(
                    'INSERT INTO "%(old_table)s" ("from_igniteuser_id", "to_igniteuser_id")'
                    ' SELECT "%(new_table)s"."child_id", "%(new_table)s"."guardian_id" FROM "%(new_table)s"'
                ) % {
                    'old_table': old_table,
                    'new_table': new_table,
                },
        )
    ]
