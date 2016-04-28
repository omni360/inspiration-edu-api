# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.utils.timezone
from django.conf import settings
import django_model_changes.changes


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0012_auto_20150630_1223'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Purchase',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('permission', models.CharField(help_text=b'The permission that the purchase grants.', max_length=50, choices=[(b'teacher', b'teach'), (b'viewer', b'view')])),
                ('project', models.ForeignKey(related_name='purchases', to='api.Project')),
                ('user', models.ForeignKey(related_name='purchases', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
            bases=(django_model_changes.changes.ChangesMixin, models.Model),
        ),
    ]
