# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0055_classroom_projects_separators'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lesson',
            name='application',
            field=models.CharField(help_text=b'The application that the lesson takes place at', max_length=50, choices=[(b'video', b'Video'), (b'123dcircuits', b'123D Circuits'), (b'tinkercad', b'Tinkercad'), (b'standalone', b'Step by step'), (b'instructables', b'Instructables'), (b'lagoa', b'Lagoa')]),
        ),
    ]
