# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0032_auto_20150824_0821'),
    ]

    operations = [
        migrations.AlterField(
            model_name='instruction',
            name='order',
            field=models.IntegerField(help_text=b'The instruction number inside the step', db_index=True),
        ),
        migrations.AlterField(
            model_name='lesson',
            name='order',
            field=models.IntegerField(db_index=True),
        ),
        migrations.AlterField(
            model_name='projectinclassroom',
            name='order',
            field=models.IntegerField(help_text=b'The order in which the project should be taken in the classroom', db_index=True),
        ),
        migrations.AlterField(
            model_name='step',
            name='order',
            field=models.IntegerField(help_text=b'The step number', db_index=True),
        ),
    ]
