# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0056_auto_20141211_1210'),
    ]

    operations = [
        migrations.AlterField(
            model_name='classroom',
            name='banner_image',
            field=models.URLField(help_text=b'A URL of a cover picture for the classroom', max_length=512, null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='classroom',
            name='card_image',
            field=models.URLField(help_text=b'A URL of a card picture for the classroom', max_length=512, null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='igniteuser',
            name='avatar',
            field=models.CharField(help_text=b"The URL of the user's avatar", max_length=512, null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='lesson',
            name='image',
            field=models.URLField(help_text=b'A URL of a cover picture for the lesson', max_length=512, null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='lesson',
            name='title',
            field=models.CharField(help_text=b"Lesson's title as it will be displayed to users", max_length=120),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='project',
            name='banner_image',
            field=models.URLField(help_text=b'A URL of a cover picture for the project', max_length=512, null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='project',
            name='card_image',
            field=models.URLField(help_text=b'A URL of a card picture for the project', max_length=512, null=True, blank=True),
            preserve_default=True,
        ),
    ]
