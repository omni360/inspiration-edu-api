# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.utils.timezone
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0059_auto_20141221_0959'),
    ]

    operations = [
        migrations.CreateModel(
            name='ClassroomInvite',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('is_deleted', models.BooleanField(default=False, db_index=True)),
                ('invitee_email', models.EmailField(max_length=75)),
                ('hash', models.CharField(unique=True, max_length=40)),
                ('accepted', models.BooleanField(default=False)),
                ('classroom', models.ForeignKey(related_name='invites', to='api.Classroom')),
                ('invitee', models.ForeignKey(related_name='classroom_invites', blank=True, to=settings.AUTH_USER_MODEL, null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
    ]
