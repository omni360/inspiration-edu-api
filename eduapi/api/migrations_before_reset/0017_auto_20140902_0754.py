# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0016_auto_20140902_0752'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='igniteuser',
            options={},
        ),
        migrations.AddField(
            model_name='course',
            name='materials_additional',
            field=models.ManyToManyField(to=b'api.Material'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='course',
            name='materials_for_sale',
            field=models.ManyToManyField(to=b'api.MaterialForSale'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='course',
            name='tools_additional',
            field=models.ManyToManyField(to=b'api.Tool'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='course',
            name='tools_for_sale',
            field=models.ManyToManyField(to=b'api.ToolForSale'),
            preserve_default=True,
        ),
    ]
