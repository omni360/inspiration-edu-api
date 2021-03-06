# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0006_lesson_students_count'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lesson',
            name='application',
            field=models.CharField(help_text=b'The application that the lesson takes place at', max_length=50, choices=[(b'123dcircuits', b'123D Circuits'), (b'tinkercad', b'Tinkercad'), (b'video', b'Video'), (b'lagoa', b'Lagoa')]),
            preserve_default=True,
        ),
    ]
