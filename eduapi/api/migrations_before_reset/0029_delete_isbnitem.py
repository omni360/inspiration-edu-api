# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0028_auto_20140918_1350'),
    ]

    operations = [
        migrations.DeleteModel(
            name='ISBNItem',
        ),
    ]
