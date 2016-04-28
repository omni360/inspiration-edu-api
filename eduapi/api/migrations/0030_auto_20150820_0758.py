# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0029_auto_20150819_1413'),
    ]

    operations = [
        migrations.AlterField(
            model_name='project',
            name='current_editor',
            field=models.ForeignKey(related_name='current_edit_projects', default=None, to=settings.AUTH_USER_MODEL, null=True),
        ),
    ]
