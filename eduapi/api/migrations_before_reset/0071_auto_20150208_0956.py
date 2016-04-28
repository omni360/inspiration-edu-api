# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class CopyLessonsWithOrderOperation(migrations.operations.base.Operation):

    def __init__(self, project_orphans_title):
        self._project_orphans_title = project_orphans_title  #this title will (hopefully) be used identity for this special project

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        '''
        Copies lessons with order from LessonInProject model into Lesson model.
        Re-used lessons in many project will be copied and referenced to the appropriate projects.
        '''

        apps = to_state.render()

        Project = apps.get_model('api', 'Project')
        Lesson = apps.get_model('api', 'Lesson')
        LessonInProject = apps.get_model('api', 'LessonInProject')
        IgniteUser = apps.get_model(settings.AUTH_USER_MODEL)
        LessonState = apps.get_model('api', 'LessonState')
        Step = apps.get_model('api', 'Step')
        db_alias = schema_editor.connection.alias

        #copy project_id and order from LessonInProject into Lesson:
        lessons_in_projects = LessonInProject.objects.using(db_alias).order_by('project', 'order')
        for lesson_in_project in lessons_in_projects:
            lesson = lesson_in_project.lesson
            orig_lesson_id = lesson.id
            #if lesson is already referenced to a project, then copy it and reference it to the project:
            if lesson.project is not None:
                lesson.id = None  #set id to 0 will create a new lesson
            #reference the lesson to the project (use the original lesson for the first project, the others are copied):
            lesson.project = lesson_in_project.project
            lesson.order = lesson_in_project.order
            lesson.save(using=db_alias)

            #if lesson was copied:
            if lesson.id != orig_lesson_id:
                orig_lesson = Lesson.objects.get(id=orig_lesson_id)

                #copy related objects of the lesson:
                orig_to_copied_steps = {}  #dict to track original -> copied step states
                related_fields = ['steps', 'teachers_files',]  #do not copy user specific related objects (like registrations and reviews)
                for related_field in related_fields:
                    #get the lesson field name in the related object:
                    related_lesson_field = next(x for x in getattr(lesson, related_field).model._meta.fields if x.rel and x.rel.to == Lesson)
                    for related_obj in getattr(orig_lesson, related_field).all():
                        orig_related_obj_pk = related_obj.pk
                        related_obj.pk = None  #unset PK to create a new copied object
                        setattr(related_obj, related_lesson_field.name, lesson)  #link the object to the new lesson
                        related_obj.save(using=db_alias)

                        #copy all instructions objects of all steps:
                        if related_field == 'steps':
                            orig_to_copied_steps[orig_related_obj_pk] = related_obj.pk  #track the copied step state
                            orig_step = related_obj._meta.model.objects.get(pk=orig_related_obj_pk)
                            for instruction_obj in orig_step.instructions.all():
                                instruction_obj.pk = None
                                instruction_obj.step = related_obj  #connect to the copied related_obj (Step)
                                instruction_obj.save()

                #copy user states of lesson and its steps, in case the user is enrolled to the project:
                #get all the lesson states that are connected to the original lesson and the user of the state has project state:
                user_lesson_states = LessonState.objects.filter(
                    lesson=orig_lesson,
                    user__projects__project=lesson_in_project.project
                )
                for user_lesson_state in user_lesson_states:
                    # print 'copy lesson state:', user_lesson_state.pk, user_lesson_state.lesson.id
                    user_lesson_step_states = list(user_lesson_state.stepstate_set.all())  #invoke
                    user_lesson_state.pk = None
                    user_lesson_state.lesson = lesson  #connect to the copied lesson
                    user_lesson_state.save()

                    #copy also all steps states of that lesson:
                    for user_lesson_step_state in user_lesson_step_states:
                        # print 'copy step state:', user_lesson_step_state.pk, user_lesson_step_state.step.id, user_lesson_step_state.step.lesson.id
                        user_lesson_step_state.pk = None
                        user_lesson_step_state.step = Step.objects.get(pk=orig_to_copied_steps[user_lesson_step_state.step.pk])  #connect to the copied step
                        user_lesson_step_state.lesson_state = user_lesson_state  #connect to the copied lesson state
                        user_lesson_step_state.save()

        #get all orphan lessons:
        orphan_lessons = Lesson.objects.using(db_alias).filter(project=None, lessoninproject__project=None)
        if orphan_lessons.exists():
            #create a new dummy project to hold all lessons that are not connected to any project:
            project_orphans = Project(
                title=self._project_orphans_title,
                description='This project was created by a data migration from LessonInProject to Lesson, and it holds all the lessons that were not connected to any project.',
                owner=IgniteUser.objects.order_by('id')[0],
                is_published=False,
            )
            project_orphans.save(using=db_alias)
            #connect orphan lessons to project_orphans:
            for order, orphan_lesson in enumerate(orphan_lessons):
                orphan_lesson.project = project_orphans
                orphan_lesson.order = order
                orphan_lesson.save(using=db_alias)

        #delete all lesson states (with their step states) where user has no project state of that lesson:
        #Note: StepState is referencing to LessonState (FK), therefore deleting the LessonState will delete all its StepState.
        #Note: LessonState of orphan lessons will be removed.
        #Note: After deletion, the deleted states are not reversible.
        LessonState.objects.exclude(
            pk__in=LessonState.objects.filter(
                lesson__project__registrations__user=models.F('user')
            )
        ).delete()

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        '''
        Copies lessons with order from Lesson into LessonInProject.
        Copied lessons from the forwards operation will not be re-used anymore.
        '''

        apps = from_state.render()

        Project = apps.get_model('api', 'Project')
        Lesson = apps.get_model('api', 'Lesson')
        LessonInProject = apps.get_model('api', 'LessonInProject')
        db_alias = schema_editor.connection.alias

        #put all lessons into LessonInProject through model:
        project_orphans = Project.objects.using(db_alias).filter(title=self._project_orphans_title).first()
        for lesson in Lesson.objects.using(db_alias).all():
            #if lesson is not in project orphans, then add it to through model:
            if not project_orphans or lesson.project.id != project_orphans.id:
                lesson_in_project = LessonInProject(
                    lesson = lesson,
                    project = lesson.project,
                    order = lesson.order,
                )
                lesson_in_project.save(using=db_alias)
            #else, if lesson is in project orphans, then ignore it:
            else:
                #disconnect lesson from orphans project:
                lesson.project = None
                lesson.save()

        #delete the orphans project:
        if project_orphans:
            project_orphans.delete()

    def state_forwards(self, app_label, state):
        pass

    def state_backwards(self, app_label, state):
        pass

    def describe(self):
        return 'Copies from LessonInProject through model into Lesson model.'


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0070_auto_20150208_0955'),
    ]

    operations = [
        CopyLessonsWithOrderOperation('#####DUMMY_PROJECT_FOR_ORPHAN_LESSONS#####')
    ]
