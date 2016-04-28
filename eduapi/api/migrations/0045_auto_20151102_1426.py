# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0044_classroom_is_archived'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lesson',
            name='application',
            field=models.CharField(help_text=b'The application that the lesson takes place at', max_length=50, choices=[(b'lagoa', b'Lagoa'), (b'standalone', b'Standalone'), (b'123dcircuits', b'123D Circuits'), (b'instructables', b'Instructables'), (b'tinkercad', b'Tinkercad'), (b'video', b'Video')]),
        ),
    ]
