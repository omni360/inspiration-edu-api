# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.utils.timezone
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0002_igniteuser_avatar'),
    ]

    operations = [
        migrations.CreateModel(
            name='PictureCourseLink',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('url', models.CharField(help_text=b'The url of the picture.', max_length=512)),
                ('course', models.ForeignKey(to='api.Course')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='VideoCourseLink',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('blob', jsonfield.fields.JSONField(help_text=b'The video resource')),
                ('course', models.ForeignKey(to='api.Course')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.AlterModelOptions(
            name='step',
            options={'ordering': (b'order',)},
        ),
        migrations.RemoveField(
            model_name='class',
            name='pictures',
        ),
        migrations.RemoveField(
            model_name='class',
            name='videos',
        ),
        migrations.RemoveField(
            model_name='course',
            name='pictures',
        ),
        migrations.DeleteModel(
            name='PictureLink',
        ),
        migrations.RemoveField(
            model_name='course',
            name='videos',
        ),
        migrations.DeleteModel(
            name='VideoLink',
        ),
        migrations.AlterField(
            model_name='course',
            name='license',
            field=models.CharField(default=b'Public Domain', help_text=b'The license that this course operates under', max_length=30, choices=[(b'CC-BY 3.0', b'CC: Attribution 3.0 Unported'), (b'CC-BY-NC 3.0', b'CC: Attribution-NonCommercial 3.0 Unported'), (b'CC-BY-SA 3.0', b'CC: Attribution-ShareAlike 3.0 Unported'), (b'CC-BY-NC-SA 3.0', b'CC: Attribution-NonCommercial-ShareAlike 3.0 Unported'), (b'Public Domain', b'Public Domain')]),
        ),
        migrations.AlterField(
            model_name='lesson',
            name='license',
            field=models.CharField(default=b'Public Domain', help_text=b'The license that this course operates under', max_length=30, choices=[(b'CC-BY 3.0', b'CC: Attribution 3.0 Unported'), (b'CC-BY-NC 3.0', b'CC: Attribution-NonCommercial 3.0 Unported'), (b'CC-BY-SA 3.0', b'CC: Attribution-ShareAlike 3.0 Unported'), (b'CC-BY-NC-SA 3.0', b'CC: Attribution-NonCommercial-ShareAlike 3.0 Unported'), (b'Public Domain', b'Public Domain')]),
        ),
    ]
