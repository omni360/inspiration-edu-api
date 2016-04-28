from django.db.models import Count
from django.core.management.base import NoArgsCommand

from api.models import Project, Lesson, Step


class Command(NoArgsCommand):
    help = """
    Update projects teacher files. Update lessons teacher files.
    """

    def handle(self, *args, **options):
        ids_projects_list = list(Project.objects.annotate(num_files=Count('teachers_files')).filter(num_files__gt=0).values_list('id', flat=True))

        projects = Project.objects.filter(id__in=set(ids_projects_list))
        for project in projects:
            if project.teachers_files.all().count() > 0:
                project.teachers_files_list = [file_obj.blob for file_obj in project.teachers_files.all()]
            project.save()

        steps = Step.objects.filter(instructions_list__len__gt=0)
        for step in steps:
            if step.instructions.all().count() > 0:
                step.instructions_list = [dict({'description': instruction.description,
                                                'image': instruction.image if instruction.image else ''})
                                          for instruction in step.instructions.all()]
            step.save()