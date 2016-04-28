# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0034_auto_20141005_0818'),
    ]

    operations = [
        migrations.AddField(
            model_name='igniteuser',
            name='is_child',
            field=models.BooleanField(default=False, help_text=b'Is the user under COPPA_CHILD_THRESHOLD years old'),
            preserve_default=True,
        ),
    ]
