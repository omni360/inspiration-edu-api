# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0030_auto_20150820_0758'),
    ]

    operations = [
        migrations.AddField(
            model_name='igniteuser',
            name='user_type',
            field=models.CharField(default=b'other', help_text=b'The user type', max_length=10, choices=[(b'teacher', b'Teacher'), (b'student', b'Student'), (b'parent', b'Parent'), (b'other', b'other')]),
        ),
    ]
