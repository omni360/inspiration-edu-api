from django.contrib.auth import get_user_model
from django.conf import settings
from django.test import TestCase
from api.models import Project, Lesson, LessonState, Step, ProjectState, StepState


class StatesLogicTests(TestCase):
    fixtures = ['test_projects_fixture_1.json']

    def setUp(self):
        self.lesson_without_steps = Lesson.objects.filter(application=settings.LESSON_APPS['Video']['db_name'])[0]
        self.lesson_with_steps = Step.objects.all()[0].lesson

    #region Lesson States
    def test_lesson_state_for_lesson_without_steps_marked_is_completed_on_init(self):
        """
        Create new state for lesson without steps (video)
        Check that it was marked completed once created.
        """

        lesson_state = LessonState.objects.create(lesson=self.lesson_without_steps, project_state_id=1)
        self.assertTrue(lesson_state.is_completed)
        #cleanup
        lesson_state.delete()

    def test_lesson_state_for_lesson_with_steps_marked_as_not_completed_on_init(self):
        """
        Create new state for lesson with steps
        Check that it was not marked completed once created.
        """

        lesson_state = LessonState.objects.create(lesson=self.lesson_with_steps, project_state_id=1)
        self.assertTrue(lesson_state.is_completed)
        #cleanup
        lesson_state.delete()

    def test_project_state_changed_according_to_lesson_states_completion(self):
        '''
        If all of the lessons are marked as completed and the ProjectState as well.
        When one of the lessons will be marked uncompleted, then the ProjectState will
        change back as well.
        '''
        project_state = ProjectState.objects.select_related(
            'project'
        ).filter(user=get_user_model().objects.get(id=2)).first()

        #add a lesson with steps:
        project_state.project.lessons.create(
            title='Lesson with steps',
            application=next(app for app,_ in Lesson.APPLICATIONS if app not in Lesson.STEPLESS_APPS),
            order=0,
        )

        # Make all of the LessonStates and mark as completed.
        lesson_states_list = []
        for lesson in project_state.project.lessons.all():

            ls, _ = LessonState.objects.update_or_create(
                project_state=project_state,
                lesson=lesson,
                defaults={
                    'is_completed': True,
                },
            )
            lesson_states_list.append(ls)

        #reload the project state, it should turn to complete
        project_state = ProjectState.objects.get(id=project_state.id)
        self.assertTrue(project_state.is_completed)

        # Revert one lesson state to incomplete
        reverted_state = project_state.lesson_states.exclude(lesson__application__in=Lesson.STEPLESS_APPS).first()  #reload
        reverted_state.is_completed = False
        reverted_state.save()

        # Reload the project state, it should turn to incomplete
        project_state = ProjectState.objects.get(id=project_state.id)
        self.assertFalse(project_state.is_completed)
        #cleanup
        for ls in lesson_states_list:
            ls.delete()

    def test_lesson_state_changed_according_to_steps_states_viewed(self):
        '''
        If all of the steps are viewed, the LessonState will be marked completed.
        When one of the steps will be removed from viewed steps, then the LessonState will
        change back to incomplete.
        '''
        project_state = ProjectState.objects.select_related(
            'project'
        ).filter(user=get_user_model().objects.get(id=2)).first()
        lesson = project_state.project.lessons.create(
            title='Lesson with steps',
            application=next(app for app,_ in Lesson.APPLICATIONS if app not in Lesson.STEPLESS_APPS),
            order=0,
        )
        lesson_state = LessonState.objects.create(
            project_state=project_state,
            lesson=lesson,
            is_completed=False,
        )

        #add some steps to the lesson:
        for i in xrange(1,4):
            lesson_state.lesson.steps.create(
                title='Step %s' %(i,),
                order=0,
            )

        # Make all of the StepStates viewed.
        step_states_list = []
        for step in lesson_state.lesson.steps.all():

            sts, _ = StepState.objects.update_or_create(
                lesson_state=lesson_state,
                step=step,
            )
            step_states_list.append(sts)

        #reload the project state, it should turn to complete
        lesson_state = LessonState.objects.get(id=lesson_state.id)
        self.assertTrue(lesson_state.is_completed)

        # Remove one step state from being viewed:
        step_states_list.pop().delete()

        # Reload the project state, it should turn to incomplete
        lesson_state = LessonState.objects.get(id=lesson_state.id)
        self.assertFalse(lesson_state.is_completed)
        #cleanup
        for sts in step_states_list:
            sts.delete()

    #endregion Lesson States