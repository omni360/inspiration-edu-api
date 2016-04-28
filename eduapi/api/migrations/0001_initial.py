# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import jsonfield.fields
import api.models.mixins
import django.utils.timezone
from django.conf import settings
import api.models.fields
from django.contrib.auth.models import Group



class AlterUniqueTogetherDeferrable(migrations.AlterUniqueTogether):
    def database_forwards(self, app_label, schema_editor, from_state, to_state, backwards=False):
        old_sql_create_unique = schema_editor.sql_create_unique
        if not backwards:
            schema_editor.sql_create_unique += 'DEFERRABLE INITIALLY IMMEDIATE'
        super(AlterUniqueTogetherDeferrable, self).database_forwards(app_label, schema_editor, from_state, to_state)
        schema_editor.sql_create_unique = old_sql_create_unique

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        self.database_forwards(app_label, schema_editor, from_state, to_state, backwards=True)


## fixtures
def add_provider_groups(apps, schema_editor):
    # create provider group for circuits
    group, created = Group.objects.get_or_create(name='123dcircuits')
    if created:
        pass
    # create provider group for tinkercad
    group, created = Group.objects.get_or_create(name='tinkercad')
    if created:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0001_initial'),
        ('contenttypes', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='IgniteUser',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(default=django.utils.timezone.now, verbose_name='last login')),
                ('is_superuser', models.BooleanField(default=False, help_text='Designates that this user has all permissions without explicitly assigning them.', verbose_name='superuser status')),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('email', models.EmailField(max_length=75, verbose_name='email address', blank=True)),
                ('is_staff', models.BooleanField(default=False, help_text='Designates whether the user can log into this admin site.', verbose_name='staff status')),
                ('is_active', models.BooleanField(default=True, help_text='Designates whether this user should be treated as active. Unselect this instead of deleting accounts.', verbose_name='active')),
                ('member_id', models.CharField(help_text=b'The Spark Drive API Member ID', unique=True, max_length=50)),
                ('oxygen_id', models.CharField(help_text=b'The Oxygen Member ID', unique=True, max_length=50)),
                ('name', models.CharField(help_text=b"The user's name", max_length=140, null=True, blank=True)),
                ('short_name', models.CharField(help_text=b"The user's short name. Could be given name or any other name in MEMBERINITIALNAME", max_length=140, null=True, blank=True)),
                ('avatar', models.CharField(help_text=b"The URL of the user's avatar", max_length=512, null=True, blank=True)),
                ('description', models.CharField(default=b'', help_text=b'The description of the user', max_length=500, blank=True)),
                ('is_child', models.BooleanField(default=False, help_text=b'Is the user under COPPA_CHILD_THRESHOLD years old')),
                ('is_verified_adult', models.BooleanField(default=False, help_text=b'Was the user verified as an adult')),
                ('is_approved', models.BooleanField(default=False, help_text=b'Does the user have a moderator')),
                ('groups', models.ManyToManyField(related_query_name='user', related_name='user_set', to='auth.Group', blank=True, help_text='The groups this user belongs to. A user will get all permissions granted to each of his/her group.', verbose_name='groups')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ChildGuardian',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('moderator_type', models.CharField(default=b'parent', max_length=50, choices=[(b'parent', b'Parent'), (b'educator', b'Educator')])),
                ('child', models.ForeignKey(related_name='childguardian_guardian_set', to=settings.AUTH_USER_MODEL)),
                ('guardian', models.ForeignKey(related_name='childguardian_child_set', to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Classroom',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('title', models.CharField(help_text=b"Classroom's title as it will be displayed to students", max_length=120)),
                ('description', models.TextField(default=b'', help_text=b"A short description of the classroom's goals and characteristics", blank=True)),
                ('banner_image', models.URLField(help_text=b'A URL of a cover picture for the classroom', max_length=512, null=True, blank=True)),
                ('card_image', models.URLField(help_text=b'A URL of a card picture for the classroom', max_length=512, null=True, blank=True)),
                ('owner', models.ForeignKey(related_name='authored_classroooms', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ClassroomInvite',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('is_deleted', models.BooleanField(default=False, db_index=True)),
                ('invitee_email', models.EmailField(max_length=75)),
                ('hash', models.CharField(unique=True, max_length=40)),
                ('accepted', models.BooleanField(default=False)),
                ('classroom', models.ForeignKey(related_name='invites', to='api.Classroom')),
                ('invitee', models.ForeignKey(related_name='classroom_invites', blank=True, to=settings.AUTH_USER_MODEL, null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ClassroomState',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('classroom', models.ForeignKey(related_name='registrations', to='api.Classroom')),
                ('user', models.ForeignKey(related_name='classrooms_states', to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Instruction',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('order', models.IntegerField(default=0, help_text=b'The instruction number inside the step', db_index=True)),
                ('description', models.TextField(help_text=b'A single instruction inside a lesson text')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Lesson',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('title', models.CharField(help_text=b"Lesson's title as it will be displayed to users", max_length=120)),
                ('description', models.TextField(default=b'', help_text=b"A short description of the lesson's goals and characteristics", blank=True)),
                ('teacher_info', models.TextField(default=b'', help_text=b'Information about the teacher who published the lesson', blank=True)),
                ('image', models.URLField(help_text=b'A URL of a cover picture for the lesson', max_length=512, null=True, blank=True)),
                ('duration', models.PositiveIntegerField(default=0, help_text=b'The expected duration of the lesson in minutes')),
                ('age', models.CharField(default=b'3+', help_text=b'The required age', max_length=10, choices=[(b'3+', b'3+'), (b'6+', b'6+'), (b'9+', b'9+'), (b'12+', b'12+'), (b'15+', b'15+'), (b'18+', b'18+')])),
                ('difficulty', models.CharField(default=b'easy', help_text=b'Difficulty level', max_length=15, choices=[(b'easy', b'Beginner'), (b'intermediate', b'Intermediate'), (b'hard', b'Advanced')])),
                ('application', models.CharField(help_text=b'The application that the lesson takes place at', max_length=50, choices=[(b'123dcircuits', b'123D Circuits'), (b'tinkercad', b'Tinkercad'), (b'video', b'Video')])),
                ('application_blob', jsonfield.fields.JSONField(default=b'', help_text=b"A JSON field that stores application specific data for presenting this step. It's recommended to use a URL", blank=True)),
                ('license', models.CharField(default=b'Public Domain', help_text=b'The license that this lesson operates under', max_length=30, choices=[(b'CC-BY 3.0', b'CC: Attribution 3.0 Unported'), (b'CC-BY-NC 3.0', b'CC: Attribution-NonCommercial 3.0 Unported'), (b'CC-BY-SA 3.0', b'CC: Attribution-ShareAlike 3.0 Unported'), (b'CC-BY-NC-SA 3.0', b'CC: Attribution-NonCommercial-ShareAlike 3.0 Unported'), (b'Public Domain', b'Public Domain')])),
                ('order', models.IntegerField(default=0, db_index=True)),
                ('owner', models.ForeignKey(related_name='authored_lessons', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('project', 'order'),
            },
            bases=(api.models.mixins.OrderedObjectInContainer, models.Model),
        ),
        migrations.CreateModel(
            name='LessonState',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('is_completed', models.BooleanField(default=False)),
                ('lesson', models.ForeignKey(related_name='registrations', to='api.Lesson')),
            ],
            options={
                'ordering': ('lesson__project', 'lesson__order'),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Material',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('description', models.CharField(max_length=512)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='MaterialForSale',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('SKU', models.CharField(max_length=128)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='PictureProjectLink',
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
        migrations.CreateModel(
            name='Project',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('is_published', models.BooleanField(default=False, db_index=True)),
                ('title', models.CharField(help_text=b"Project's title as it will be displayed to students", max_length=120)),
                ('description', models.TextField(default=b'', help_text=b"A short description of the project's goals and characteristics", blank=True)),
                ('banner_image', models.URLField(help_text=b'A URL of a cover picture for the project', max_length=512, null=True, blank=True)),
                ('card_image', models.URLField(help_text=b'A URL of a card picture for the project', max_length=512, null=True, blank=True)),
                ('duration', models.PositiveIntegerField(default=0, help_text=b'The expected duration of the lesson in minutes')),
                ('age', models.CharField(default=b'3+', help_text=b'The required age', max_length=10, choices=[(b'3+', b'3+'), (b'6+', b'6+'), (b'9+', b'9+'), (b'12+', b'12+'), (b'15+', b'15+'), (b'18+', b'18+')])),
                ('difficulty', models.CharField(default=b'easy', help_text=b'Difficulty level', max_length=15, choices=[(b'easy', b'Beginner'), (b'intermediate', b'Intermediate'), (b'hard', b'Advanced')])),
                ('license', models.CharField(default=b'Public Domain', help_text=b'The license that this project operates under', max_length=30, choices=[(b'CC-BY 3.0', b'CC: Attribution 3.0 Unported'), (b'CC-BY-NC 3.0', b'CC: Attribution-NonCommercial 3.0 Unported'), (b'CC-BY-SA 3.0', b'CC: Attribution-ShareAlike 3.0 Unported'), (b'CC-BY-NC-SA 3.0', b'CC: Attribution-NonCommercial-ShareAlike 3.0 Unported'), (b'Public Domain', b'Public Domain')])),
                ('teacher_info', models.TextField(default=b'', help_text=b'Information about the teacher who published the lesson', blank=True)),
                ('tags', api.models.fields.TagsField(default=b'', max_length=150, blank=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ProjectInClassroom',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('order', models.IntegerField(default=0, help_text=b'The order in which the project should be taken in the classroom', db_index=True)),
                ('classroom', models.ForeignKey(related_name='projects_through_set', to='api.Classroom')),
                ('project', models.ForeignKey(to='api.Project')),
            ],
            options={
                'ordering': ['classroom', 'order'],
            },
            bases=(api.models.mixins.OrderedObjectInContainer, models.Model),
        ),
        migrations.CreateModel(
            name='ProjectState',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('is_completed', models.BooleanField(default=False)),
                ('project', models.ForeignKey(related_name='registrations', to='api.Project')),
                ('user', models.ForeignKey(related_name='projects', to=settings.AUTH_USER_MODEL)),
                ('viewed_lessons', models.ManyToManyField(to='api.Lesson', through='api.LessonState')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Review',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('is_deleted', models.BooleanField(default=False, db_index=True)),
                ('object_id', models.PositiveIntegerField(db_index=True)),
                ('text', models.CharField(max_length=500)),
                ('rating', models.IntegerField(choices=[(1, 1), (2, 2), (3, 3), (4, 4), (5, 5), (6, 6), (7, 7), (8, 8), (9, 9), (10, 10)])),
                ('content_type', models.ForeignKey(to='contenttypes.ContentType')),
                ('owner', models.ForeignKey(related_name='reviews', to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Step',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('order', models.IntegerField(default=0, help_text=b'The step number', db_index=True)),
                ('title', models.CharField(help_text=b'The title as it will appear to the user', max_length=255)),
                ('description', models.TextField(default=b'', help_text=b'A short description', blank=True)),
                ('image', models.URLField(help_text=b'A URL of an image that will accompany the step', null=True, blank=True)),
                ('hint', models.TextField(default=b'', help_text=b'A hint to help complete the step', blank=True)),
                ('application_blob', jsonfield.fields.JSONField(default=b'', help_text=b"A JSON field that stores application specific data for presenting this step. It's recommended to use a URL", blank=True)),
                ('lesson', models.ForeignKey(related_name='steps', to='api.Lesson')),
            ],
            options={
                'ordering': ('order',),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='StepState',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('state', models.CharField(max_length=50, blank=True)),
                ('lesson_state', models.ForeignKey(related_name='step_states', to='api.LessonState')),
                ('step', models.ForeignKey(to='api.Step')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TeachersFileLessonLink',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('blob', jsonfield.fields.JSONField(help_text=b'The file resource')),
                ('lesson', models.ForeignKey(related_name='teachers_files', to='api.Lesson')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TeachersFileProjectLink',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('blob', jsonfield.fields.JSONField(help_text=b'The file resource')),
                ('project', models.ForeignKey(related_name='teachers_files', to='api.Project')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Tool',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('description', models.CharField(max_length=512)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ToolForSale',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('SKU', models.CharField(max_length=128)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='VideoProjectLink',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('added', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('updated', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('blob', jsonfield.fields.JSONField(help_text=b'The video resource')),
                ('project', models.ForeignKey(related_name='videos', to='api.Project')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='stepstate',
            unique_together=set([('step', 'lesson_state')]),
        ),
        migrations.AlterUniqueTogether(
            name='step',
            unique_together=set([('lesson', 'order')]),
        ),
        migrations.AlterUniqueTogether(
            name='review',
            unique_together=set([('owner', 'content_type', 'object_id')]),
        ),
        migrations.AlterUniqueTogether(
            name='projectstate',
            unique_together=set([('user', 'project')]),
        ),
        migrations.AlterUniqueTogether(
            name='projectinclassroom',
            # unique_together=set([('project', 'classroom'), ('classroom', 'order')]),
            unique_together=set([('project', 'classroom')]),
        ),
        migrations.AddField(
            model_name='project',
            name='classrooms',
            field=models.ManyToManyField(related_name='projects', through='api.ProjectInClassroom', to='api.Classroom'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='project',
            name='materials_additional',
            field=models.ManyToManyField(to='api.Material', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='project',
            name='materials_for_sale',
            field=models.ManyToManyField(to='api.MaterialForSale', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='project',
            name='owner',
            field=models.ForeignKey(related_name='authored_projects', to=settings.AUTH_USER_MODEL),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='project',
            name='tools_additional',
            field=models.ManyToManyField(to='api.Tool', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='project',
            name='tools_for_sale',
            field=models.ManyToManyField(to='api.ToolForSale', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='pictureprojectlink',
            name='project',
            field=models.ForeignKey(related_name='pictures', to='api.Project'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='lessonstate',
            name='project_state',
            field=models.ForeignKey(related_name='lesson_states', to='api.ProjectState'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='lessonstate',
            name='viewed_steps',
            field=models.ManyToManyField(to='api.Step', through='api.StepState'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='lessonstate',
            unique_together=set([('project_state', 'lesson')]),
        ),
        migrations.AddField(
            model_name='lesson',
            name='project',
            field=models.ForeignKey(related_name='lessons', to='api.Project'),
            preserve_default=True,
        ),
        # migrations.AlterUniqueTogether(
        #     name='lesson',
        #     unique_together=set([('project', 'order')]),
        # ),
        migrations.AddField(
            model_name='instruction',
            name='step',
            field=models.ForeignKey(related_name='instructions', to='api.Step'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='classroomstate',
            unique_together=set([('user', 'classroom')]),
        ),
        migrations.AddField(
            model_name='classroom',
            name='students',
            field=models.ManyToManyField(related_name='classrooms', through='api.ClassroomState', to=settings.AUTH_USER_MODEL),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='childguardian',
            unique_together=set([('child', 'guardian')]),
        ),
        migrations.AddField(
            model_name='igniteuser',
            name='guardians',
            field=models.ManyToManyField(related_name='children', through='api.ChildGuardian', to=settings.AUTH_USER_MODEL, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='igniteuser',
            name='user_permissions',
            field=models.ManyToManyField(related_query_name='user', related_name='user_set', to='auth.Permission', blank=True, help_text='Specific permissions for this user.', verbose_name='user permissions'),
            preserve_default=True,
        ),


        # unique-together defferable alterations
        AlterUniqueTogetherDeferrable(
            name='projectinclassroom',
            unique_together=set([('project', 'classroom'),('classroom', 'order')]),
        ),
        AlterUniqueTogetherDeferrable(
            name='lesson',
            unique_together=set([('project', 'order')]),
        ),


        # fixtures
        migrations.RunPython(add_provider_groups),
    ]
