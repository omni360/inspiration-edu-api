# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0019_auto_20150720_0830'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='min_publish_date',
            field=models.DateTimeField(null=True, db_index=True),
        ),
        migrations.AddField(
            model_name='project',
            name='publish_mode',
            field=models.CharField(default=b'edit', max_length=50, db_index=True, choices=[(b'edit', b'In Edit'), (b'review', b'In Review'), (b'ready', b'Ready For Publish'), (b'published', b'Published')]),
        ),
    ]
