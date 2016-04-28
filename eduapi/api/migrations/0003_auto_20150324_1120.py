# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0002_auto_20150311_1725'),
    ]

    operations = [
        migrations.AddField(
            model_name='classroomstate',
            name='status',
            field=models.CharField(default=b'approved', help_text=b'User enroll status', max_length=30, choices=[(b'approved', b'Approved'), (b'pending', b'Pending'), (b'rejected', b'Rejected')]),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='classroom',
            name='code',
            field=models.CharField(help_text=b'Classroom code for users to join the classroom', max_length=8, unique=True, null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='classroom',
            name='owner',
            field=models.ForeignKey(related_name='authored_classrooms', to=settings.AUTH_USER_MODEL),
            preserve_default=True,
        ),
    ]
