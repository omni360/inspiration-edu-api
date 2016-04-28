# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import jsonfield.fields
import api.models.models
import django.contrib.postgres.fields


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0024_merge'),
    ]

    operations = [
        migrations.AddField(
            model_name='lesson',
            name='teachers_files_list',
            field=django.contrib.postgres.fields.ArrayField(size=None, null=True, base_field=jsonfield.fields.JSONField(), blank=True),
        ),
        migrations.AddField(
            model_name='project',
            name='picture_links_list',
            field=django.contrib.postgres.fields.ArrayField(size=None, null=True, base_field=models.URLField(max_length=512), blank=True),
        ),
        migrations.AddField(
            model_name='project',
            name='teachers_files_list',
            field=django.contrib.postgres.fields.ArrayField(size=None, null=True, base_field=jsonfield.fields.JSONField(), blank=True),
        ),
        migrations.AddField(
            model_name='project',
            name='video_links_list',
            field=django.contrib.postgres.fields.ArrayField(size=None, null=True, base_field=jsonfield.fields.JSONField(), blank=True),
        ),
        migrations.AddField(
            model_name='step',
            name='instructions_list',
            field=django.contrib.postgres.fields.ArrayField(size=None, null=True, base_field=jsonfield.fields.JSONField(), blank=True),
        ),
    ]
