# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0068_auto_20150127_1218'),
    ]

    operations = [
        migrations.AlterField(
            model_name='project',
            name='materials_additional',
            field=models.ManyToManyField(to='api.Material', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='project',
            name='materials_for_sale',
            field=models.ManyToManyField(to='api.MaterialForSale', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='project',
            name='tools_additional',
            field=models.ManyToManyField(to='api.Tool', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='project',
            name='tools_for_sale',
            field=models.ManyToManyField(to='api.ToolForSale', blank=True),
            preserve_default=True,
        ),
    ]
