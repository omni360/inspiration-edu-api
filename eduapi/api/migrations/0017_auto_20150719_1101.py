# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.utils.timezone
import django_model_changes.changes


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0016_auto_20150713_1058'),
    ]

    operations = [
        migrations.CreateModel(
            name='ViewInvite',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('hash', models.CharField(default=b'gl4Lr1OttoPNG14I_iKHV9DMmNE09R9jDZ7z9Swh0fKN3wCvfAM74RPWmHdM7Rqguxfkqzv6XKOSLFsX_aZ2qBxLN2UeW7vA6yTMswc5oR4j3YGwc9cEnZPcmy8bB2mqsxPzLu-A7QmE', unique=True, max_length=140)),
            ],
            options={
                'abstract': False,
            },
            bases=(django_model_changes.changes.ChangesMixin, models.Model),
        ),
        migrations.AlterField(
            model_name='childguardian',
            name='added',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
        migrations.AlterField(
            model_name='classroom',
            name='added',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
        migrations.AlterField(
            model_name='classroominvite',
            name='added',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
        migrations.AlterField(
            model_name='classroomstate',
            name='added',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
        migrations.AlterField(
            model_name='delegateinvite',
            name='added',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
        migrations.AlterField(
            model_name='igniteuser',
            name='added',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
        migrations.AlterField(
            model_name='instruction',
            name='added',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
        migrations.AlterField(
            model_name='lesson',
            name='added',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
        migrations.AlterField(
            model_name='lessonstate',
            name='added',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
        migrations.AlterField(
            model_name='material',
            name='added',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
        migrations.AlterField(
            model_name='materialforsale',
            name='added',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
        migrations.AlterField(
            model_name='ownerdelegate',
            name='added',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
        migrations.AlterField(
            model_name='pictureprojectlink',
            name='added',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
        migrations.AlterField(
            model_name='project',
            name='added',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
        migrations.AlterField(
            model_name='projectinclassroom',
            name='added',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
        migrations.AlterField(
            model_name='projectstate',
            name='added',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
        migrations.AlterField(
            model_name='review',
            name='added',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
        migrations.AlterField(
            model_name='step',
            name='added',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
        migrations.AlterField(
            model_name='stepstate',
            name='added',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
        migrations.AlterField(
            model_name='teachersfilelessonlink',
            name='added',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
        migrations.AlterField(
            model_name='teachersfileprojectlink',
            name='added',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
        migrations.AlterField(
            model_name='tool',
            name='added',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
        migrations.AlterField(
            model_name='toolforsale',
            name='added',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
        migrations.AlterField(
            model_name='videoprojectlink',
            name='added',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
        migrations.AddField(
            model_name='viewinvite',
            name='project',
            field=models.OneToOneField(related_name='view_invite', to='api.Project'),
        ),
    ]
