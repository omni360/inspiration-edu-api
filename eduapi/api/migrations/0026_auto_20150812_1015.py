# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
# from django.apps import apps
from django.db.models import Count

def move_objects_to_json(apps, schema_editor):
    Project = apps.get_model('api', 'Project')
    Lesson = apps.get_model('api', 'Lesson')
    Step = apps.get_model('api', 'Step')

    ids_projects_list = list(Project.objects.annotate(num_files=Count('teachers_files')).filter(num_files__gt=0).values_list('id', flat=True))
    ids_projects_list += list(Project.objects.annotate(num_pictures=Count('pictures')).filter(num_pictures__gt=0).values_list('id', flat=True))
    ids_projects_list += list(Project.objects.annotate(num_videos=Count('videos')).filter(num_videos__gt=0).values_list('id', flat=True))

    projects = Project.objects.filter(id__in=set(ids_projects_list))
    for project in projects:
        if project.teachers_files.all().count() > 0:
            project.teachers_files_list = [file_obj.blob for file_obj in project.teachers_files.all()]
        if project.videos.all().count() > 0:
            project.videos_list = [video.blob for video in project.videos.all()]
        if project.pictures.all().count() > 0:
            project.pictures_list = [picture.url for picture in project.pictures.all()]
        project.save()

    lessons = Lesson.objects.annotate(num_files=Count('teachers_files')).filter(num_files__gt=0)
    for lesson in lessons:
        if lesson.teachers_files.all().count() > 0:
            lesson.teachers_files_list = [file_obj.blob for file_obj in lesson.teachers_files.all()]
        lesson.save()

    steps = Step.objects.filter(instructions_count__gt=0)
    for step in steps:
        if step.instructions.all().count() > 0:
            step.instructions_list = [dict({'description': instruction.description,
                                            'image': instruction.image if instruction.image else '',
                                            'order': instruction.order,
                                            'id': instruction.id})
                                      for instruction in step.instructions.all()]
        step.save()

def move_json_to_objects(apps, schema_editor):
    Project = apps.get_model('api', 'Project')
    Lesson = apps.get_model('api', 'Lesson')
    Step = apps.get_model('api', 'Step')
    Instruction = apps.get_model('api', 'Instruction')
    TeachersFileLessonLink = apps.get_model('api', 'TeachersFileLessonLink')
    TeachersFileProjectLink = apps.get_model('api', 'TeachersFileProjectLink')
    VideoProjectLink = apps.get_model('api', 'VideoProjectLink')
    PictureProjectLink = apps.get_model('api', 'PictureProjectLink')

    projects = Project.objects.filter(teachers_files_list__len__gt=0)
    for project in projects:
        teacher_files = [TeachersFileProjectLink(project=project, blob=blob) for blob in project.teachers_files_list]
        TeachersFileProjectLink.objects.bulk_create(teacher_files)

    projects = Project.objects.filter(teachers_files_list__len__gt=0)
    for project in projects:
        teacher_files = [PictureProjectLink(project=project, blob=blob) for blob in project.picture_links_list]
        PictureProjectLink.objects.bulk_create(teacher_files)

    projects = Project.objects.filter(video_links_list__len__gt=0)
    for project in projects:
        teacher_files = [VideoProjectLink(project=project, blob=blob) for blob in project.video_links_list]
        VideoProjectLink.objects.bulk_create(teacher_files)

    lessons = Lesson.objects.filter(picture_links_list__len__gt=0)
    for lesson in lessons:
        teacher_files = [TeachersFileLessonLink(lesson=lesson, blob=blob) for blob in lesson.teachers_files_list]
        TeachersFileLessonLink.objects.bulk_create(teacher_files)

    steps = Step.objects.filter(instructions_list__len__gt=0)
    for step in steps:
        instructions = [Instruction(step=step,
                                    order=idx,
                                    description=instruction.get('description'),
                                    image=instruction.image if instruction.image else '') for idx, instruction in enumerate(step.instructions_list)]
        Instruction.objects.bulk_create(instructions)


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0025_auto_20150812_1011'),
    ]

    operations = [
        migrations.RunPython(move_objects_to_json,
                             move_json_to_objects)
    ]
