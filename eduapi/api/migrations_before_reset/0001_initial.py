# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import jsonfield.fields
import django.utils.timezone
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='IgniteUser',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(default=django.utils.timezone.now, verbose_name='last login')),
                ('is_superuser', models.BooleanField(default=False, help_text='Designates that this user has all permissions without explicitly assigning them.', verbose_name='superuser status')),
                ('username', models.CharField(help_text='Required. 30 characters or fewer. Letters, digits and @/./+/-/_ only.', unique=True, max_length=30, verbose_name='username', validators=[django.core.validators.RegexValidator('^[\\w.@+-]+$', 'Enter a valid username.', 'invalid')])),
                ('first_name', models.CharField(max_length=30, verbose_name='first name', blank=True)),
                ('last_name', models.CharField(max_length=30, verbose_name='last name', blank=True)),
                ('email', models.EmailField(max_length=75, verbose_name='email address', blank=True)),
                ('is_staff', models.BooleanField(default=False, help_text='Designates whether the user can log into this admin site.', verbose_name='staff status')),
                ('is_active', models.BooleanField(default=True, help_text='Designates whether this user should be treated as active. Unselect this instead of deleting accounts.', verbose_name='active')),
                ('date_joined', models.DateTimeField(default=django.utils.timezone.now, verbose_name='date joined')),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('member_id', models.CharField(help_text=b'The Spark Drive API Member ID', unique=True, max_length=50)),
                ('name', models.CharField(help_text=b"The user's name", max_length=140, null=True, blank=True)),
                ('short_name', models.CharField(help_text=b"The user's short name. Could be given name or any other name in MEMBERINITIALNAME", max_length=140, null=True, blank=True)),
                ('groups', models.ManyToManyField(to='auth.Group', verbose_name='groups', blank=True)),
                ('user_permissions', models.ManyToManyField(to='auth.Permission', verbose_name='user permissions', blank=True)),
            ],
            options={
                'abstract': False,
                'verbose_name': 'user',
                'verbose_name_plural': 'users',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Class',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('is_published', models.BooleanField(default=False)),
                ('title', models.CharField(help_text=b"Course's title as it will be displayed to users", max_length=120)),
                ('description', models.TextField(default=b'', help_text=b"A short description of the course's goals and characteristics", blank=True)),
                ('banner_image', models.URLField(help_text=b'A URL of a cover picture for the course', null=True, blank=True)),
                ('card_image', models.URLField(help_text=b'A URL of a card picture for the course', null=True, blank=True)),
                ('duration', models.PositiveIntegerField(default=0, help_text=b'The expected duration of the lesson in minutes')),
                ('age', models.CharField(default=b'3+', help_text=b'The required age', max_length=10, choices=[(b'3+', b'3+'), (b'6+', b'6+'), (b'9+', b'9+'), (b'12+', b'12+'), (b'15+', b'15+'), (b'18+', b'18+')])),
                ('difficulty', models.CharField(default=b'easy', help_text=b'Difficulty level', max_length=15, choices=[(b'easy', b'Easy'), (b'intermediate', b'Intermediate'), (b'hard', b'Hard')])),
                ('teacher_info', models.TextField(default=b'', help_text=b'Information about the teacher who published the lesson', blank=True)),
                ('license', models.CharField(default=b'Public Domain', help_text=b'The license that this course operates under', max_length=30, choices=[(b'CC-BY 3.0', b'CC-BY 3.0'), (b'CC-BY-NC 3.0', b'CC-BY-NC 3.0'), (b'CC-BY-SA 3.0', b'CC-BY-SA 3.0'), (b'CC-BY-NC-SA 3.0', b'CC-BY-NC-SA 3.0'), (b'Public Domain', b'Public Domain')])),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Course',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('is_published', models.BooleanField(default=False)),
                ('title', models.CharField(help_text=b"Course's title as it will be displayed to users", max_length=120)),
                ('description', models.TextField(default=b'', help_text=b"A short description of the course's goals and characteristics", blank=True)),
                ('banner_image', models.URLField(help_text=b'A URL of a cover picture for the course', null=True, blank=True)),
                ('card_image', models.URLField(help_text=b'A URL of a card picture for the course', null=True, blank=True)),
                ('duration', models.PositiveIntegerField(default=0, help_text=b'The expected duration of the lesson in minutes')),
                ('age', models.CharField(default=b'3+', help_text=b'The required age', max_length=10, choices=[(b'3+', b'3+'), (b'6+', b'6+'), (b'9+', b'9+'), (b'12+', b'12+'), (b'15+', b'15+'), (b'18+', b'18+')])),
                ('difficulty', models.CharField(default=b'easy', help_text=b'Difficulty level', max_length=15, choices=[(b'easy', b'Easy'), (b'intermediate', b'Intermediate'), (b'hard', b'Hard')])),
                ('teacher_info', models.TextField(default=b'', help_text=b'Information about the teacher who published the lesson', blank=True)),
                ('license', models.CharField(default=b'Public Domain', help_text=b'The license that this course operates under', max_length=30, choices=[(b'CC-BY 3.0', b'CC-BY 3.0'), (b'CC-BY-NC 3.0', b'CC-BY-NC 3.0'), (b'CC-BY-SA 3.0', b'CC-BY-SA 3.0'), (b'CC-BY-NC-SA 3.0', b'CC-BY-NC-SA 3.0'), (b'Public Domain', b'Public Domain')])),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Instruction',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('order', models.IntegerField(default=0, help_text=b'The instruction number inside the step')),
                ('description', models.TextField(help_text=b'A single instruction inside a lesson text')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ISBNItem',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('name', models.CharField(help_text=b'The name of this ISBN item.', max_length=256)),
                ('isbn', models.CharField(help_text=b'Numeric ISBN, hyphens are allowed.', max_length=32)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='course',
            name='tools',
            field=models.ManyToManyField(to='api.ISBNItem'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='course',
            name='materials',
            field=models.ManyToManyField(to='api.ISBNItem'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='class',
            name='tools',
            field=models.ManyToManyField(to='api.ISBNItem'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='class',
            name='materials',
            field=models.ManyToManyField(to='api.ISBNItem'),
            preserve_default=True,
        ),
        migrations.CreateModel(
            name='Lesson',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('is_published', models.BooleanField(default=False)),
                ('title', models.CharField(help_text=b"Lesson's title as it will be displayed to users", max_length=70)),
                ('description', models.TextField(default=b'', help_text=b"A short description of the lesson's goals and characteristics", blank=True)),
                ('teacher_info', models.TextField(default=b'', help_text=b'Information about the teacher who published the lesson', blank=True)),
                ('image', models.URLField(help_text=b'A URL of a cover picture for the lesson', null=True, blank=True)),
                ('duration', models.PositiveIntegerField(default=0, help_text=b'The expected duration of the lesson in minutes')),
                ('age', models.CharField(default=b'3+', help_text=b'The required age', max_length=10, choices=[(b'3+', b'3+'), (b'6+', b'6+'), (b'9+', b'9+'), (b'12+', b'12+'), (b'15+', b'15+'), (b'18+', b'18+')])),
                ('difficulty', models.CharField(default=b'easy', help_text=b'Difficulty level', max_length=15, choices=[(b'easy', b'Easy'), (b'intermediate', b'Intermediate'), (b'hard', b'Hard')])),
                ('application', models.CharField(help_text=b'The application that the lesson takes place at', max_length=50, choices=[(b'123dcircuits', b'123D Circuits'), (b'tinkercad', b'Tinkercad'), (b'instructables', b'Instructables'), (b'video', b'Video')])),
                ('application_blob', jsonfield.fields.JSONField(default=b'', help_text=b"A JSON field that stores application specific data for presenting this step. It's recommended to use a URL", blank=True)),
                ('license', models.CharField(default=b'Public Domain', help_text=b'The license that this course operates under', max_length=30, choices=[(b'CC-BY 3.0', b'CC-BY 3.0'), (b'CC-BY-NC 3.0', b'CC-BY-NC 3.0'), (b'CC-BY-SA 3.0', b'CC-BY-SA 3.0'), (b'CC-BY-NC-SA 3.0', b'CC-BY-NC-SA 3.0'), (b'Public Domain', b'Public Domain')])),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='LessonInClass',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('order', models.IntegerField(default=0, help_text=b'The order in which the lesson should be taken in the class')),
                ('class_obj', models.ForeignKey(to='api.Class')),
            ],
            options={
                'ordering': [b'class_obj', b'order'],
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='lesson',
            name='classes',
            field=models.ManyToManyField(to='api.Class', through='api.LessonInClass'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='lessoninclass',
            name='lesson',
            field=models.ForeignKey(to='api.Lesson'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='lessoninclass',
            unique_together=set([(b'lesson', b'class_obj', b'order')]),
        ),
        migrations.CreateModel(
            name='LessonInCourse',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('order', models.IntegerField(default=0, help_text=b'The order in which the lesson should be taken in the course')),
                ('course', models.ForeignKey(to='api.Course')),
            ],
            options={
                'ordering': [b'course', b'order'],
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='lesson',
            name='courses',
            field=models.ManyToManyField(to='api.Course', through='api.LessonInCourse'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='lessonincourse',
            name='lesson',
            field=models.ForeignKey(to='api.Lesson'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='lessonincourse',
            unique_together=set([(b'lesson', b'course', b'order')]),
        ),
        migrations.CreateModel(
            name='PictureLink',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('url', models.CharField(help_text=b'The url of the picture.', max_length=512)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='course',
            name='pictures',
            field=models.ManyToManyField(to='api.PictureLink'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='class',
            name='pictures',
            field=models.ManyToManyField(to='api.PictureLink'),
            preserve_default=True,
        ),
        migrations.CreateModel(
            name='Step',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('is_deleted', models.BooleanField(default=False, db_index=True)),
                ('order', models.IntegerField(default=0, help_text=b'The step number')),
                ('type', models.IntegerField(default=2, help_text=b'The step type', choices=[(1, b'Video'), (2, b'Lecture')])),
                ('title', models.CharField(help_text=b'The title as it will appear to the user', max_length=255)),
                ('description', models.TextField(default=b'', help_text=b'A short description', blank=True)),
                ('image', models.URLField(help_text=b'A URL of an image that will accompany the step', null=True, blank=True)),
                ('hint', models.TextField(default=b'', help_text=b'A hint to help complete the step', blank=True)),
                ('application_blob', jsonfield.fields.JSONField(default=b'', help_text=b"A JSON field that stores application specific data for presenting this step. It's recommended to use a URL", blank=True)),
                ('lesson', models.ForeignKey(to='api.Lesson')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='instruction',
            name='step',
            field=models.ForeignKey(to='api.Step'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='step',
            unique_together=set([(b'lesson', b'order')]),
        ),
        migrations.CreateModel(
            name='VideoLink',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('url', models.CharField(help_text=b'The url of the video.', max_length=512)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='course',
            name='videos',
            field=models.ManyToManyField(to='api.VideoLink'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='class',
            name='videos',
            field=models.ManyToManyField(to='api.VideoLink'),
            preserve_default=True,
        ),
    ]
