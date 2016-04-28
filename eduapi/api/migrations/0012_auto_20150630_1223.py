# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0011_auto_20150621_1604'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='lock',
            field=models.IntegerField(default=0, help_text=b'A locked project is a project that only people with a certain permission can view/teach', choices=[(0, b'None'), (1, b'Bundle')]),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='project',
            name='sys_message',
            field=models.TextField(default=b'', help_text=b"A system message that's assciated with this project", blank=True),
            preserve_default=True,
        ),
    ]
