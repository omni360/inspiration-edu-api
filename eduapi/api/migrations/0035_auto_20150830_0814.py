# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0034_auto_20150826_1142'),
    ]

    operations = [
        migrations.AlterField(
            model_name='project',
            name='current_editor',
            field=models.ForeignKey(related_name='current_edit_projects', blank=True, to=settings.AUTH_USER_MODEL, null=True),
        ),
        migrations.AlterField(
            model_name='project',
            name='min_publish_date',
            field=models.DateTimeField(db_index=True, null=True, blank=True),
        ),
    ]
