# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0021_igniteuser_guardian'),
    ]

    operations = [
        migrations.AlterField(
            model_name='review',
            name='owner',
            field=models.ForeignKey(related_name=b'reviews', to=settings.AUTH_USER_MODEL),
        ),
    ]
