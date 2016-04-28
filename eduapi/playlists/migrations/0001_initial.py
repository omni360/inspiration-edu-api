# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.utils.timezone
import django.contrib.postgres.fields
import django_model_changes.changes


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Playlist',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('title', models.CharField(max_length=256)),
                ('description', models.CharField(max_length=512, null=True, blank=True)),
                ('project_id_list', django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(), size=None)),
                ('priority', models.IntegerField(default=0)),
                ('is_published', models.BooleanField(default=False)),
            ],
            options={
                'ordering': ('priority',),
            },
            bases=(django_model_changes.changes.ChangesMixin, models.Model),
        ),
    ]
