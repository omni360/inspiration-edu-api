# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.contrib.postgres.fields


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0056_auto_20160104_0951'),
    ]

    operations = [
        migrations.AlterField(
            model_name='project',
            name='subject',
            field=django.contrib.postgres.fields.ArrayField(size=None, null=True, base_field=models.CharField(max_length=25, choices=[(b'art', b'Art'), (b'drama', b'Drama'), (b'geography', b'Geography'), (b'history', b'History'), (b'language arts', b'Language Arts'), (b'math', b'Math'), (b'music', b'Music'), (b'science', b'Science'), (b'social studies', b'Social Studies'), (b'technology', b'Technology')]), blank=True),
        ),
    ]
