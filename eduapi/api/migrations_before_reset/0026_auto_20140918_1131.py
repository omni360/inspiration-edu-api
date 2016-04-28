# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0025_auto_20140916_0706'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='class',
            name='materials',
        ),
        migrations.RemoveField(
            model_name='class',
            name='tools',
        ),
        migrations.AddField(
            model_name='class',
            name='materials_additional',
            field=models.ManyToManyField(to='api.Material'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='class',
            name='materials_for_sale',
            field=models.ManyToManyField(to='api.MaterialForSale'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='class',
            name='owner',
            field=models.ForeignKey(related_name=b'authored_classes', default=2, to=settings.AUTH_USER_MODEL),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='class',
            name='tools_additional',
            field=models.ManyToManyField(to='api.Tool'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='class',
            name='tools_for_sale',
            field=models.ManyToManyField(to='api.ToolForSale'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='class',
            name='license',
            field=models.CharField(default=b'Public Domain', help_text=b'The license that this course operates under', max_length=30, choices=[(b'CC-BY 3.0', b'CC: Attribution 3.0 Unported'), (b'CC-BY-NC 3.0', b'CC: Attribution-NonCommercial 3.0 Unported'), (b'CC-BY-SA 3.0', b'CC: Attribution-ShareAlike 3.0 Unported'), (b'CC-BY-NC-SA 3.0', b'CC: Attribution-NonCommercial-ShareAlike 3.0 Unported'), (b'Public Domain', b'Public Domain')]),
        ),
        migrations.AlterField(
            model_name='class',
            name='title',
            field=models.CharField(help_text=b"Course's title as it will be displayed to students", max_length=120),
        ),
        migrations.AlterField(
            model_name='course',
            name='title',
            field=models.CharField(help_text=b"Course's title as it will be displayed to students", max_length=120),
        ),
    ]
