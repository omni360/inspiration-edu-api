# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0024_auto_20140908_2338'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='review',
            unique_together=set([('owner', 'content_type', 'object_id')]),
        ),
    ]
