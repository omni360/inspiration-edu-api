# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django_model_changes.changes
import django.utils.timezone
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0015_project_current_editor_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='DelegateInvite',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('is_deleted', models.BooleanField(default=False, db_index=True)),
                ('invitee_email', models.EmailField(max_length=254)),
                ('hash', models.CharField(unique=True, max_length=40)),
                ('accepted', models.BooleanField(default=False)),
                ('invitee', models.ForeignKey(related_name='delegator_invites', blank=True, to=settings.AUTH_USER_MODEL, null=True)),
                ('owner', models.ForeignKey(related_name='delegate_invites', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
            bases=(django_model_changes.changes.ChangesMixin, models.Model),
        ),
        migrations.CreateModel(
            name='OwnerDelegate',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('owner', models.ForeignKey(related_name='ownerdelegate_delegate_set', to=settings.AUTH_USER_MODEL)),
                ('user', models.ForeignKey(related_name='ownerdelegate_delegator_set', to=settings.AUTH_USER_MODEL)),
            ],
            bases=(django_model_changes.changes.ChangesMixin, models.Model),
        ),
        migrations.AddField(
            model_name='igniteuser',
            name='delegates',
            field=models.ManyToManyField(related_name='delegators', through='api.OwnerDelegate', to=settings.AUTH_USER_MODEL, blank=True),
        ),
        migrations.AlterUniqueTogether(
            name='ownerdelegate',
            unique_together=set([('owner', 'user')]),
        ),
    ]
