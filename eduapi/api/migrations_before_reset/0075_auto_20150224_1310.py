# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0074_merge'),
    ]

    operations = [
        migrations.AlterField(
            model_name='igniteuser',
            name='is_approved',
            field=models.BooleanField(default=False, help_text=b'Does the user have a moderator'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='lesson',
            name='application',
            field=models.CharField(help_text=b'The application that the lesson takes place at', max_length=50, choices=[(b'123dcircuits', b'123D Circuits'), (b'tinkercad', b'Tinkercad'), (b'video', b'Video')]),
            preserve_default=True,
        ),
    ]
