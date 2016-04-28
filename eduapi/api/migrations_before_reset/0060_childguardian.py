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
            name='ChildGuardian',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('moderator_type', models.CharField(default=b'parent', max_length=50, choices=[(b'parent', b'Parent'), (b'educator', b'Educator')])),
                ('child', models.ForeignKey(related_name='child', to=settings.AUTH_USER_MODEL)),
                ('guardian', models.ForeignKey(related_name='guardian', to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='childguardian',
            unique_together=set([('child', 'guardian')]),
        ),
    ]
