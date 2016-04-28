# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0010_remove_lesson_owner'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lesson',
            name='application',
            field=models.CharField(help_text=b'The application that the lesson takes place at', max_length=50, choices=[(b'123dcircuits', b'123D Circuits'), (b'lagoa', b'Lagoa'), (b'tinkercad', b'Tinkercad'), (b'video', b'Video')]),
            preserve_default=True,
        ),
    ]
