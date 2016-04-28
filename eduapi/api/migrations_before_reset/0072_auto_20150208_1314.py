# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0071_auto_20150208_0956'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='lessoninproject',
            unique_together=None,
        ),
        migrations.RemoveField(
            model_name='lessoninproject',
            name='lesson',
        ),
        migrations.RemoveField(
            model_name='lessoninproject',
            name='project',
        ),
        migrations.RemoveField(
            model_name='lesson',
            name='projects',
        ),
        migrations.DeleteModel(
            name='LessonInProject',
        ),
        migrations.AlterField(
            model_name='lesson',
            name='order',
            field=models.IntegerField(default=0, db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='lesson',
            name='project',
            field=models.ForeignKey(related_name='lessons', to='api.Project'),
            preserve_default=True,
        ),
    ]
