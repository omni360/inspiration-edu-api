# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0049_auto_20151116_1428'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='teachersfilelessonlink',
            name='lesson',
        ),
        migrations.RemoveField(
            model_name='teachersfileprojectlink',
            name='project',
        ),
        migrations.AlterField(
            model_name='lesson',
            name='application',
            field=models.CharField(help_text=b'The application that the lesson takes place at', max_length=50, choices=[(b'standalone', b'Step by step'), (b'lagoa', b'Lagoa'), (b'123dcircuits', b'123D Circuits'), (b'instructables', b'Instructables'), (b'tinkercad', b'Tinkercad'), (b'video', b'Video')]),
        ),
        migrations.DeleteModel(
            name='TeachersFileLessonLink',
        ),
        migrations.DeleteModel(
            name='TeachersFileProjectLink',
        ),
    ]
