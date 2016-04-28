# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0067_merge'),
    ]

    operations = [
        migrations.AlterField(
            model_name='childguardian',
            name='child',
            field=models.ForeignKey(related_name='childguardian_guardian_set', to=settings.AUTH_USER_MODEL),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='childguardian',
            name='guardian',
            field=models.ForeignKey(related_name='childguardian_child_set', to=settings.AUTH_USER_MODEL),
            preserve_default=True,
        ),
    ]
