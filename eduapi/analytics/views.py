from django.core.cache import cache
from django.utils.timezone import now as utc_now

from rest_framework import generics
from rest_framework.response import Response
from analytics.permissions import ProjectAnalyticsPermission

from models import Project


class ProjectAnalyticsView(generics.RetrieveAPIView):
    permission_classes = (ProjectAnalyticsPermission,)

    def get(self, request, *args, **kwargs):
        #todo: add permissions
        project = self.get_object()
        cached_project_analytics = cache.get('project_analytics_%s' % project.id)
        if cached_project_analytics and not request.query_params.get('hardRefresh', False):
            return Response(cached_project_analytics)
        else:
            project_lessons_list = list(project.lessons.all())  # materialize list to avoid database access (ordered by order by default)
            data = {
                'usersStartedProject': project.students_count,
                'usersCompletedProject': project.registrations.filter(is_completed=True).count(),
                'lessonsOrder': [x.id for x in project_lessons_list],
                'lessonsTitles': {lesson.id: lesson.title for lesson in project_lessons_list},
                'usersStartedLessons': {lesson.id: lesson.registrations.all().count() for lesson in project_lessons_list},
                'usersCompletedLessons': {lesson.id: lesson.registrations.filter(is_completed=True).count() for lesson in project_lessons_list},
                'usersCompletedSteps': {
                    lesson.id: {
                        step.order: step.stepstate_set.all().count() for step in lesson.steps.all()
                        } for lesson in project_lessons_list
                    },
                'analyticsLastUpdated': utc_now(),
            }
            cache.set('project_analytics_%s' % project.id, data, timeout=24*60*60)

            return Response(data)

    def get_queryset(self):
        return Project.objects.all()

