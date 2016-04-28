# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.utils.timezone
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contenttypes', '0001_initial'),
        ('api', '0012_merge'),
    ]

    operations = [
        migrations.CreateModel(
            name='Review',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('is_deleted', models.BooleanField(default=False, db_index=True)),
                ('object_id', models.PositiveIntegerField()),
                ('text', models.CharField(max_length=500)),
                ('rating', models.IntegerField(default=1, choices=[(1, 1), (2, 2), (3, 3), (4, 4), (5, 5), (6, 6), (7, 7), (8, 8), (9, 9)])),
                ('author', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
                ('content_type', models.ForeignKey(to='contenttypes.ContentType')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.AlterModelOptions(
            name='igniteuser',
            options={},
        ),
    ]
