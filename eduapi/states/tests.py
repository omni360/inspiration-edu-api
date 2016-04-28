import urlparse
from django.contrib.auth import get_user_model
from django.conf import settings
from django.db.models import Count
from rest_framework.test import APITestCase
from django.core.urlresolvers import reverse
from api.models import LessonState, Lesson, Project, ProjectState, StepState


class StepStateTests(APITestCase):
    fixtures = ['test_projects_fixture_1.json']

    @classmethod
    def setUpTestData(cls):
        cls.student_user = get_user_model().objects.get(name='Darth Doe')
        cls.lesson = Lesson.objects.annotate(step_count=Count('steps')).filter(step_count__gt=0, project__publish_mode=Project.PUBLISH_MODE_PUBLISHED)[0]
        cls.project_state = ProjectState.objects.create(project=cls.lesson.project,
                                                        user=cls.student_user)
        cls.lesson_state = LessonState.objects.create(lesson=cls.lesson,
                                                      project_state=cls.project_state,)

    def test_add_step_state(self):
        step_states_count = self.lesson_state.step_states.count()
        self.client.force_authenticate(self.student_user)
        # Create step
        response = self.client.post(reverse('api:step-state-create',
                                            kwargs={
                                                'project_pk': self.lesson.project.id,
                                                'lesson_pk': self.lesson.id
                                            }),
                                    {
                                        'step': self.lesson.steps.all()[0].id,
                                    })
        # Check that step state created
        self.assertEqual(response.status_code, 201)
        self.assertGreater(self.lesson_state.step_states.count(), step_states_count)

    def test_delete_step_state(self):
        step_states_count = self.lesson_state.viewed_steps.count()
        # First create step state
        self.client.force_authenticate(self.student_user)
        response = self.client.post(reverse('api:step-state-create',
                                            kwargs={
                                                'project_pk': self.lesson.project.id,
                                                'lesson_pk': self.lesson.id
                                            }),
                                    {
                                        'step': self.lesson.steps.all()[0].id,
                                    })
        self.assertEqual(response.status_code, 201)

        # Second try to delete it
        step_state = self.lesson_state.step_states.all()[0]
        step_order = step_state.step.order
        self.client.delete(reverse('api:step-state-delete',
                                            kwargs={
                                                'project_pk': self.lesson.project.id,
                                                'lesson_pk': self.lesson.id,
                                                'order': step_order
                                            }),)
        self.assertEqual(StepState.objects.filter(id=step_state.id).count(), 0)
        self.assertEqual(self.lesson_state.viewed_steps.count(), step_states_count)

    def test_start_learning_new_lesson_state_created(self):
        self.client.force_authenticate(self.student_user)
        response = self.client.get(reverse('api:lesson-start', kwargs={
                                                'project_pk': self.lesson.project.id,
                                                'lesson_pk': self.lesson.project.lessons.exclude(pk=self.lesson.pk)[0].id
        }) + '?no-redirect=True')
        self.assertEqual(response.status_code, 201)

    def test_start_learning_already_started_lesson_state_created(self):
        self.client.force_authenticate(self.student_user)
        lesson_to_start = self.lesson.project.lessons.exclude(pk=self.lesson.pk)[0]
        response = self.client.get(reverse('api:lesson-start', kwargs={
                                                'project_pk': self.lesson.project.id,
                                                'lesson_pk': lesson_to_start.id
        }) + '?no-redirect=True')
        self.assertEqual(response.status_code, 201)
        response = self.client.get(reverse('api:lesson-start', kwargs={
                                                'project_pk': self.lesson.project.id,
                                                'lesson_pk': lesson_to_start.id
        }) + '?no-redirect=True')
        self.assertEqual(response.status_code, 200)


    def _check_redirect(self, lesson, query_params, expected_url, expected_query_params, add_project_lesson_to_query=True):
        response = self.client.get(reverse('api:lesson-start', kwargs={
                                                'project_pk': lesson.project.id,
                                                'lesson_pk': lesson.id
        }), query_params)
        self.assertEqual(response.status_code, 302)

        redirect_url = response.url
        redirect_parsed = urlparse.urlparse(redirect_url)
        redirect_query_params = dict(urlparse.parse_qsl(redirect_parsed.query))
        if add_project_lesson_to_query:
            expected_query_params.update({
                'edu-project-id': str(lesson.project.id),
                'edu-lesson-id': str(lesson.id),
            })

        self.assertTrue(redirect_url.startswith(expected_url))
        self.assertDictEqual(redirect_query_params, expected_query_params)

    def _check_no_redirect(self, lesson, query_params):
        no_redirect_query_params = {}
        no_redirect_query_params.update(query_params)
        no_redirect_query_params.update({'no-redirect': 'true'})
        response = self.client.get(reverse('api:lesson-start', kwargs={
                                                'project_pk': lesson.project.id,
                                                'lesson_pk': lesson.id
        }), no_redirect_query_params)
        self.assertIn(response.status_code, [200, 201])

    def test_redirect_tinkercad(self):
        self.client.force_authenticate(self.student_user)

        lesson_state = self.lesson_state
        lesson = lesson_state.lesson
        lesson.application = settings.LESSON_APPS['Tinkercad']['db_name']
        lesson.save()

        query_params = {
            'edu-project-id': '99999',
            'edu-param-1': 'param1',
            'edu-document-id': '*FAKE-REMOVED*',
        }

        # lesson without canvas document id
        lesson_url = settings.LESSON_APPS['Tinkercad']['lesson_url']
        self._check_redirect(lesson, query_params, lesson_url, {
            'edu-param-1': query_params['edu-param-1'],
        })

        # lesson with default init canvas id
        default_canvas_document_id = 'DEFAULT-CANVAS-123'
        lesson.project.extra = {
            'lessonsInit': [{
                'lessonsIds': [lesson.id],
                'application': lesson.application,
                'initCanvasId': default_canvas_document_id,
            }]
        }
        lesson.project.save()
        self._check_redirect(lesson, query_params, lesson_url, {
            'edu-param-1': query_params['edu-param-1'],
            'edu-document-id': default_canvas_document_id,
            'edu-document-copy': 'true',
        })

        # lesson with user state canvas document id
        canvas_document_id = 'ABC123'
        lesson_state.extra = {'canvasDocumentId': canvas_document_id}
        lesson_state.save()
        self._check_redirect(lesson, query_params, lesson_url, {
            'edu-param-1': query_params['edu-param-1'],
            'edu-document-id': canvas_document_id,
        })

    def test_redirect_circuits(self):
        self.client.force_authenticate(self.student_user)

        lesson_state = self.lesson_state
        lesson = lesson_state.lesson
        lesson.application = settings.LESSON_APPS['Circuits']['db_name']
        lesson.save()

        query_params = {
            'edu-project-id': '99999',
            'edu-param-1': 'param1',
            'edu-document-id': '*FAKE-PASSED*',
        }

        # lesson without canvas document id
        lesson_url = settings.LESSON_APPS['Circuits']['lesson_url']
        self._check_redirect(lesson, query_params, lesson_url, {
            'edu-param-1': query_params['edu-param-1'],
            'edu-document-id': query_params['edu-document-id'],
        })

        # lesson with default init canvas id
        default_canvas_document_id = 'DEFAULT-CANVAS-123'
        lesson.project.extra = {
            'lessonsInit': [{
                'lessonsIds': [lesson.id],
                'application': lesson.application,
                'initCanvasId': default_canvas_document_id,
            }]
        }
        lesson.project.save()
        self._check_redirect(lesson, query_params, lesson_url, {
            'edu-param-1': query_params['edu-param-1'],
            'edu-document-id': query_params['edu-document-id'],
        })

        # lesson with user state canvas document id
        canvas_document_id = 'ABC123'
        lesson_state.extra = {'canvasDocumentId': canvas_document_id}
        lesson_state.save()
        lesson_with_id_url = settings.LESSON_APPS['Circuits']['lesson_with_id_url']
        query_params.update({
            'edu-circuit-id': canvas_document_id,
            'edu-member-id': self.student_user.member_id
        })
        self._check_redirect(lesson, query_params, lesson_with_id_url, {
            'edu-param-1': query_params['edu-param-1'],
            'edu-document-id': query_params['edu-document-id'],
            'edu-circuit-id': canvas_document_id,
            'edu-member-id': query_params['edu-member-id'],
        })

    def test_redirect_video_and_others(self):
        self.client.force_authenticate(self.student_user)

        for lesson_app in ['Video', 'Step by step']:

            lesson_state = self.lesson_state
            lesson = lesson_state.lesson
            lesson.application = settings.LESSON_APPS[lesson_app]['db_name']
            lesson.save()

            query_params = {
                'edu-project-id': '99999',
                'edu-param-1': 'param1',
                'edu-document-id': '*FAKE-PASSED*',
            }

            # lesson without canvas document id
            lesson_url = settings.LESSON_APPS[lesson_app]['lesson_url'] + 'project/{}/lesson/{}/'.format(lesson.project.id, lesson.id)
            self._check_redirect(lesson, query_params, lesson_url, {}, add_project_lesson_to_query=False)

            # lesson with default init canvas id
            default_canvas_document_id = 'DEFAULT-CANVAS-123'
            lesson.project.extra = {
                'lessonsInit': [{
                    'lessonsIds': [lesson.id],
                    'application': lesson.application,
                    'initCanvasId': default_canvas_document_id,
                }]
            }
            lesson.project.save()
            self._check_redirect(lesson, query_params, lesson_url, {}, add_project_lesson_to_query=False)

            # lesson with user state canvas document id
            canvas_document_id = 'ABC123'
            lesson_state.extra = {'canvasDocumentId': canvas_document_id}
            lesson_state.save()
            self._check_redirect(lesson, query_params, lesson_url, {}, add_project_lesson_to_query=False)

    def test_redirect_lagoa_not_implemented(self):
        self.client.force_authenticate(self.student_user)

        lesson_state = self.lesson_state
        lesson = lesson_state.lesson
        lesson.application = settings.LESSON_APPS['Lagoa']['db_name']
        lesson.save()

        response = self.client.get(reverse('api:lesson-start', kwargs={
                                                'project_pk': lesson.project.id,
                                                'lesson_pk': lesson.id
        }))
        self.assertEqual(response.status_code, 501)  # Not Implemented

    def test_no_redirect_all_lessons(self):
        self.client.force_authenticate(self.student_user)

        for app, app_info in settings.LESSON_APPS.items():

            lesson_state = self.lesson_state
            lesson = lesson_state.lesson
            lesson.application = app_info['db_name']
            lesson.save()

            query_params = {
                'edu-project-id': '99999',
                'edu-param-1': 'param1',
                'edu-document-id': '*FAKE-PASSED*',
            }

            # lesson without canvas document id
            self._check_no_redirect(lesson, query_params)

            # lesson with default init canvas id
            default_canvas_document_id = 'DEFAULT-CANVAS-123'
            lesson.project.extra = {
                'lessonsInit': [{
                    'lessonsIds': [lesson.id],
                    'application': lesson.application,
                    'initCanvasId': default_canvas_document_id,
                }]
            }
            lesson.project.save()
            self._check_no_redirect(lesson, query_params)

            # lesson with user state canvas document id
            canvas_document_id = 'ABC123'
            lesson_state.extra = {'canvasDocumentId': canvas_document_id}
            lesson_state.save()
            self._check_no_redirect(lesson, query_params)
