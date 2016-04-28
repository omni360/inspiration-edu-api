# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0048_merge'),
    ]

    operations = [
        migrations.AddField(
            model_name='lesson',
            name='draft_origin',
            field=models.OneToOneField(related_name='draft_object', null=True, default=None, to='api.Lesson'),
        ),
        migrations.AddField(
            model_name='project',
            name='draft_origin',
            field=models.OneToOneField(related_name='draft_object', null=True, default=None, to='api.Project'),
        ),
        migrations.AddField(
            model_name='step',
            name='draft_origin',
            field=models.OneToOneField(related_name='draft_object', null=True, default=None, to='api.Step'),
        ),
    ]
