from django.apps import AppConfig, apps
from django_counter_field import connect_counter


class ApiConfig(AppConfig):
    name = 'api'
    verbose_name = 'Ignite Api'

    def ready(self):
        # import signal handlers

        #region Counters registrations
        # Student counter for Classroom
        connect_counter('students_approved_count',
                        apps.get_model('api', 'ClassroomState').classroom,
                        lambda state: state.status == 'approved')
        connect_counter('students_rejected_count',
                        apps.get_model('api', 'ClassroomState').classroom,
                        lambda state: state.status == 'rejected')
        connect_counter('students_pending_count',
                        apps.get_model('api', 'ClassroomState').classroom,
                        lambda state: state.status == 'pending')
        # Projects counter for Project
        connect_counter('projects_count',
                        apps.get_model('api', 'ProjectInClassroom').classroom)

        # Lesson counter for Project
        connect_counter('lesson_count',
                        apps.get_model('api', 'Lesson').project,
                        lambda obj: obj.is_deleted == False)
        # Student counter for Project
        connect_counter('students_count',
                        apps.get_model('api', 'ProjectState').project)

        # Coeditors counter for User Project owner
        connect_counter('editors_count',
                        apps.get_model('api', 'OwnerDelegate').owner)

        # Steps counter for Lesson
        connect_counter('steps_count',
                        apps.get_model('api', 'Step').lesson,
                        lambda obj: obj.is_deleted == False)
        connect_counter('students_count',
                        apps.get_model('api', 'LessonState').lesson)

        # Lessons Started/Finished counter for Project State
        connect_counter('enrolled_lessons_count',
                        apps.get_model('api', 'LessonState').project_state)
        connect_counter('completed_lessons_count',
                        apps.get_model('api', 'LessonState').project_state,
                        lambda state: state.is_completed)

        #endregion Counters registrations