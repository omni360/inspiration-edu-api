# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0044_auto_20141118_1228'),
    ]

    operations = [
        migrations.AlterField(
            model_name='course',
            name='tags',
            field=models.CharField(default=b'', max_length=150, blank=True, validators=[django.core.validators.RegexValidator(b'^((?!\\s*(?:,|$))[\\w\\s-]+,?)*$', b'Enter slugs separated by comma')]),
            preserve_default=True,
        ),
    ]
