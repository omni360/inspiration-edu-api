# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0040_auto_20141019_1549'),
    ]

    operations = [
        migrations.AlterField(
            model_name='classroom',
            name='difficulty',
            field=models.CharField(default=b'easy', help_text=b'Difficulty level', max_length=15, choices=[(b'easy', b'Beginner'), (b'intermediate', b'Intermediate'), (b'hard', b'Advanced')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='classroom',
            name='is_published',
            field=models.BooleanField(default=False, db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='course',
            name='difficulty',
            field=models.CharField(default=b'easy', help_text=b'Difficulty level', max_length=15, choices=[(b'easy', b'Beginner'), (b'intermediate', b'Intermediate'), (b'hard', b'Advanced')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='course',
            name='is_published',
            field=models.BooleanField(default=False, db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='instruction',
            name='order',
            field=models.IntegerField(default=0, help_text=b'The instruction number inside the step', db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='lesson',
            name='difficulty',
            field=models.CharField(default=b'easy', help_text=b'Difficulty level', max_length=15, choices=[(b'easy', b'Beginner'), (b'intermediate', b'Intermediate'), (b'hard', b'Advanced')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='lesson',
            name='is_published',
            field=models.BooleanField(default=False, db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='lessoninclassroom',
            name='order',
            field=models.IntegerField(default=0, help_text=b'The order in which the lesson should be taken in the classroom', db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='lessonincourse',
            name='order',
            field=models.IntegerField(default=0, help_text=b'The order in which the lesson should be taken in the course', db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='review',
            name='object_id',
            field=models.PositiveIntegerField(db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='step',
            name='order',
            field=models.IntegerField(default=0, help_text=b'The step number', db_index=True),
            preserve_default=True,
        ),
    ]
