import json
import unittest

from django.db.models import Count, Q, F
from django.core.urlresolvers import reverse
from django.contrib.auth import get_user_model
from django.core import management
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder

from rest_framework.test import APITestCase as DRFTestCase

from api.models import Step, Lesson, Project, ClassroomState, ProjectState, LessonState, ProjectInClassroom


# TODO: Inherit from EduTestCase
class StateTests(DRFTestCase):
    """
    Tests the ProjectState and LessonState API.
    """

    fixtures = ['test_projects_fixture_1.json']

    def setUp(self):
        self.global_user_1 = get_user_model().objects.get(id=2)
        self.global_user_2 = get_user_model().objects.get(id=4)

        self.api_project_list_url = reverse('api:project-list')
        self.api_project_detail_url = reverse('api:project-detail',  kwargs={'pk': 1})
        self.api_project_state_not_enrolled_url = reverse('api:project-state-detail',  kwargs={'project_pk': 2})
        self.api_project_state_not_enrolled_unpublished_url = reverse('api:project-state-detail',  kwargs={'project_pk': 5})

        self.api_classroom_list_url = reverse('api:classroom-list')
        self.api_classroom_detail_url = reverse('api:classroom-detail',  kwargs={'pk': 4})
        self.api_classroom_state_not_enrolled_url = reverse('api:classroom-state-detail',  kwargs={'classroom_pk': 2})

        self.project = Project.objects.annotate(num_lessons=Count('lessons')).filter(publish_mode=Project.PUBLISH_MODE_PUBLISHED, num_lessons__gte=1)[0]
        self.project_unpublished = Project.objects.annotate(num_lessons=Count('lessons')).filter(publish_mode=Project.PUBLISH_MODE_EDIT, num_lessons__gte=1)[0]
        self.api_lesson_list_url = reverse('api:project-lesson-list', kwargs={'project_pk': self.project.id})
        self.api_lesson_detail_url = reverse('api:project-lesson-detail',  kwargs={'project_pk': self.project.id, 'pk': self.project.lessons.all()[0].id})
        self.lesson_enrolled_qs = self.project.lessons.filter(registrations__project_state__user=self.global_user_1)
        self.api_lesson_state_not_enrolled_url = reverse('api:project-lesson-state-detail',  kwargs={
            'project_pk': self.project.id,
            'lesson_pk': self.project.lessons.exclude(id__in=self.lesson_enrolled_qs)[0].id
        })
        self.api_lesson_state_not_enrolled_unpublished_url = reverse('api:project-lesson-state-detail',  kwargs={
            'project_pk': self.project_unpublished.id,
            'lesson_pk': self.project_unpublished.lessons.exclude(id__in=self.lesson_enrolled_qs)[0].id
        })
        self.lesson_obj = Lesson.objects.get(pk=1)

    # Anonymous user
    # ##############

    def test_anonymous_user_doesnt_have_classroom_state(self):
        """
        Make sure that no 'enrolled', 'state' attributes return
        when an unauthenticated user requests classrooms.
        """
        self.client.force_authenticate(None)
        resp = self.client.get(self.api_classroom_list_url)
        self.assertEqual(resp.status_code, 401)

    def test_anonymous_user_doesnt_have_project_state(self):
        """
        Make sure that no 'enrolled', 'state' attributes return
        when an unauthenticated user requests projects.
        """
        self.client.force_authenticate(None)
        data = self.client.get(self.api_project_list_url).data

        for item in data.get('results'):
            self.assertNotIn('enrolled', item)
            self.assertNotIn('state', item)

    def test_anonymous_user_doesnt_have_lesson_state(self):
        """
        Make sure that no 'state' attribute return
        when an unauthenticated user requests lessons.
        """
        self.client.force_authenticate(None)
        data = self.client.get(self.api_lesson_list_url).data

        for item in data.get('results'):
            self.assertNotIn('state', item)

    # Classroom Enrollment
    # ####################

    def test_classroom_state_counters(self):
        """
        Make sure the classroom state counters are correct.
        """
        #build counters:
        management.call_command('rebuild_counters')

        self.client.force_authenticate(self.global_user_1)
        data = self.client.get(self.api_classroom_list_url, {'user': 'current'}).data['results']

        for classroom_data in data:
            self.assertIn('state', classroom_data)
            classroom_state_data = classroom_data['state']
            if classroom_state_data:
                classroom_state_obj = ClassroomState.objects.get(classroom=classroom_state_data['id'], user=classroom_state_data['userId'])
                self.assertEqual(classroom_state_data['numberOfClassroomProjects'], classroom_state_obj.classroom.projects.count())
                self.assertEqual(
                    classroom_state_data['numberOfEnrolledProjects'],
                    ProjectState.objects.filter(
                        project__in=classroom_state_obj.classroom.projects.all(),
                        user=classroom_state_obj.user
                    ).count()
                )
                self.assertEqual(
                    classroom_state_data['numberOfCompletedProjects'],
                    ProjectState.objects.filter(
                        project__in=classroom_state_obj.classroom.projects.all(),
                        user=classroom_state_obj.user,
                        is_completed=True
                    ).count()
                )

    def test_user_enrolled_to_classroom(self):
        """
        Make sure that the global user is enrolled to a specific classroom.
        """
        self.client.force_authenticate(self.global_user_1)
        data = self.client.get(self.api_classroom_detail_url, {'user': 'current'}).data

        self.assertTrue(data.get('enrolled'))

    def test_user_not_enrolled_to_classroom(self):
        """
        Make sure that the global user is not enrolled to a specific classroom.
        """
        self.client.force_authenticate(self.global_user_1)
        resp = self.client.get(self.api_classroom_state_not_enrolled_url)

        # Make sure nothing is found - not enrolled.
        self.assertEqual(resp.status_code, 404)

    def test_user_can_not_enroll_to_classroom(self):
        """
        Make sure that a user cannot enroll to a classroom.
        Students are added to classroom by the classroom teacher that makes PUT to classrooms-students-detail view.
        """
        self.client.force_authenticate(self.global_user_1)

        # Make sure nothing is found - not enrolled.
        resp = self.client.get(self.api_classroom_state_not_enrolled_url)
        self.assertEqual(resp.status_code, 404)

        # POST and make sure the user is not enrolled by herself:
        resp = self.client.post(self.api_classroom_state_not_enrolled_url)
        self.assertEqual(resp.status_code, 405)
        resp = self.client.get(self.api_classroom_state_not_enrolled_url)
        self.assertEqual(resp.status_code, 404)

    # Project Enrollment
    # #################

    def test_project_state_counters(self):
        """
        Make sure the project state counters are correct.
        """
        #build counters:
        management.call_command('rebuild_counters')

        self.client.force_authenticate(self.global_user_1)
        data = self.client.get(self.api_project_list_url, {'user': 'current'}).data['results']

        for project_data in data:
            self.assertIn('state', project_data)
            project_state_data = project_data['state']
            if project_state_data:
                project_state_obj = ProjectState.objects.get(project=project_state_data['id'], user=project_state_data['userId'])
                self.assertEqual(project_state_data['numberOfProjectLessons'], project_state_obj.project.lessons.count())
                self.assertEqual(
                    project_state_data['numberOfEnrolledLessons'],
                    project_state_obj.lesson_states.count()
                )
                self.assertEqual(
                    project_state_data['numberOfCompletedLessons'],
                    project_state_obj.lesson_states.filter(is_completed=True).count()
                )

    def test_user_enrolled_to_project(self):
        """
        Make sure that the global user is enrolled to a specific project.
        """
        self.client.force_authenticate(self.global_user_1)

        data = self.client.get(self.api_project_detail_url, {'user': 'current'}).data

        self.assertTrue(data.get('enrolled'))

    def test_user_not_enrolled_to_project(self):
        """
        Make sure that the global user is not enrolled to a specific project.
        """
        self.client.force_authenticate(self.global_user_1)
        resp = self.client.get(self.api_project_state_not_enrolled_url)

        # Make sure nothing is found - not enrolled.
        self.assertEqual(resp.status_code, 404)

    def test_user_can_enroll_to_published_project(self):
        """
        Make sure that an authenticated user can enroll to a published project.
        """
        self.client.force_authenticate(self.global_user_1)

        # Make sure nothing is found - not enrolled.
        resp = self.client.get(self.api_project_state_not_enrolled_url)
        self.assertEqual(resp.status_code, 404)

        # POST and make sure the user is enrolled
        resp = self.client.post(self.api_project_state_not_enrolled_url)
        self.assertIn(resp.status_code, xrange(200, 202))
        resp = self.client.get(self.api_project_state_not_enrolled_url)
        self.assertEqual(resp.status_code, 200)

        # POST like the above, but with an empty object:
        # NOTE: DRF sets default value for BooleanField when request.data is instance of QueryDict,
        #       and request.data is <QueryDict {}> when no payload is given, and regular dict when payload is {...}.
        resp = self.client.post(self.api_project_state_not_enrolled_url, {})
        self.assertIn(resp.status_code, xrange(200, 202))
        resp = self.client.get(self.api_project_state_not_enrolled_url)
        self.assertEqual(resp.status_code, 200)

    def test_user_can_not_enroll_to_unpublished_project(self):
        """
        Make sure that an authenticated user can not enroll to an unpublished project.
        """
        self.client.force_authenticate(self.global_user_1)

        # Make sure nothing is found - not enrolled.
        resp = self.client.get(self.api_project_state_not_enrolled_unpublished_url)
        self.assertEqual(resp.status_code, 404)

        #NOTE: Allowed!
        # # POST and make sure the user is enrolled
        # resp = self.client.post(self.api_project_state_not_enrolled_unpublished_url)
        # self.assertEqual(resp.status_code, 403)
        # resp = self.client.get(self.api_project_state_not_enrolled_unpublished_url)
        # self.assertEqual(resp.status_code, 404)

    # Lesson Enrollment
    # #################

    def test_lesson_state_counters(self):
        """
        Make sure the lesson state counters are correct.
        """
        #build counters:
        management.call_command('rebuild_counters')

        self.client.force_authenticate(self.global_user_1)
        data = self.client.get(self.api_lesson_list_url, {'user': 'current'}).data['results']

        for lesson_data in data:
            self.assertIn('state', lesson_data)
            lesson_state_data = lesson_data['state']
            if lesson_state_data:
                lesson_state_obj = LessonState.objects.get(lesson=lesson_state_data['id'], project_state__user=lesson_state_data['userId'])
                self.assertEqual(lesson_state_data['numberOfLessonSteps'], lesson_state_obj.lesson.steps.count())
                self.assertEqual(len(lesson_state_data['viewedSteps']), lesson_state_obj.step_states.count())

    def test_user_can_enroll_to_published_lesson(self):
        """
        Make sure that an authenticated user can enroll to a published lesson.
        """
        self.client.force_authenticate(self.global_user_1)

        # Make sure nothing is found - not enrolled.
        resp = self.client.get(self.api_lesson_state_not_enrolled_url)
        self.assertEqual(resp.status_code, 404)

        # POST and make sure the user is enrolled
        resp = self.client.post(self.api_lesson_state_not_enrolled_url)
        self.assertIn(resp.status_code, xrange(200, 202))
        resp = self.client.get(self.api_lesson_state_not_enrolled_url)
        self.assertEqual(resp.status_code, 200)

        # POST like the above, but with an empty object:
        # NOTE: DRF sets default value for BooleanField when request.data is instance of QueryDict,
        #       and request.data is <QueryDict {}> when no payload is given, and regular dict when payload is {...}.
        resp = self.client.post(self.api_lesson_state_not_enrolled_url, {})
        self.assertIn(resp.status_code, xrange(200, 202))
        resp = self.client.get(self.api_lesson_state_not_enrolled_url)
        self.assertEqual(resp.status_code, 200)

    def test_user_can_not_enroll_to_unpublished_lesson(self):
        """
        Make sure that an authenticated user can not enroll to an unpublished lesson.
        """
        self.client.force_authenticate(self.global_user_1)

        # Make the unpublished project owned by the authenticated user:
        self.project_unpublished.owner = self.global_user_1
        self.project_unpublished.save()

        # Make sure nothing is found - not enrolled.
        resp = self.client.get(self.api_lesson_state_not_enrolled_unpublished_url)
        self.assertEqual(resp.status_code, 404)

        #NOTE: Allowed!
        # # POST and make sure the user is enrolled
        # resp = self.client.post(self.api_lesson_state_not_enrolled_unpublished_url)
        # self.assertEqual(resp.status_code, 403)
        # resp = self.client.get(self.api_lesson_state_not_enrolled_unpublished_url)
        # self.assertEqual(resp.status_code, 404)

        # Other user (that do not have access to the project)

        # Make the unpublished project owned by a user that is not child or delegator of the authenticated user:
        new_owner = get_user_model().objects.exclude(
            Q(pk=self.global_user_1.pk) |
            Q(pk__in=self.global_user_1.delegators.all()) |
            Q(pk__in=self.global_user_1.children.all())
        )[0]
        self.project_unpublished.owner = new_owner
        self.project_unpublished.save()

        # Make sure nothing is found - not enrolled.
        resp = self.client.get(self.api_lesson_state_not_enrolled_unpublished_url)
        self.assertEqual(resp.status_code, 404)

        # POST and make sure the user is enrolled
        resp = self.client.post(self.api_lesson_state_not_enrolled_unpublished_url)
        self.assertEqual(resp.status_code, 404)
        resp = self.client.get(self.api_lesson_state_not_enrolled_unpublished_url)
        self.assertEqual(resp.status_code, 404)

    def test_user_enroll_to_lesson_automatically_enroll_to_parent_project(self):
        """
        Make sure that an authenticated user that enrolls to a lesson, automatically enrolls to its parent project
        if not enrolled to yet.
        """
        #get lessons that their parent project is not enrolled:
        project_lesson_not_enrolled_qs = Lesson.objects.exclude(
            Q(id__in=self.lesson_enrolled_qs) |
            Q(project__id__in=Project.objects.filter(registrations__user=self.global_user_1))
        )

        ### lesson of published project:

        #get a lesson that its parent project is not enrolled and published:
        project_lesson_not_enrolled_published_obj = project_lesson_not_enrolled_qs.filter(
            project__publish_mode=Project.PUBLISH_MODE_PUBLISHED
        ).first()

        self.client.force_authenticate(self.global_user_1)

        #make sure nothing is found - not enrolled.
        api_project_lesson_not_enrolled_state = reverse('api:project-lesson-state-detail', kwargs={
            'project_pk': project_lesson_not_enrolled_published_obj.project_id,
            'lesson_pk': project_lesson_not_enrolled_published_obj.id
        })
        resp = self.client.get(api_project_lesson_not_enrolled_state)
        self.assertEqual(resp.status_code, 404)
        api_project_not_enrolled_state = reverse('api:project-state-detail', kwargs={
            'project_pk': project_lesson_not_enrolled_published_obj.project_id
        })
        resp = self.client.get(api_project_not_enrolled_state)
        self.assertEqual(resp.status_code, 404)

        #POST and make sure the user is enrolled
        resp = self.client.post(api_project_lesson_not_enrolled_state)
        self.assertIn(resp.status_code, xrange(200, 202))
        resp = self.client.get(api_project_lesson_not_enrolled_state)
        self.assertEqual(resp.status_code, 200)

        #make sure the parent project state was automatically created
        resp = self.client.get(api_project_not_enrolled_state)
        self.assertEqual(resp.status_code, 200)

        #lesson of unpublished project:

        #get a lesson that its parent project is not enrolled and unpublished:
        project_lesson_not_enrolled_unpublished_obj = project_lesson_not_enrolled_qs.filter(
            project__publish_mode=Project.PUBLISH_MODE_EDIT,
            project__owner=self.global_user_1,
        ).first()

        #make sure nothing is found - not enrolled.
        api_project_lesson_not_enrolled_state = reverse('api:project-lesson-state-detail', kwargs={
            'project_pk': project_lesson_not_enrolled_unpublished_obj.project_id,
            'lesson_pk': project_lesson_not_enrolled_unpublished_obj.id
        })
        resp = self.client.get(api_project_lesson_not_enrolled_state)
        self.assertEqual(resp.status_code, 404)
        api_project_not_enrolled_state = reverse('api:project-state-detail', kwargs={
            'project_pk': project_lesson_not_enrolled_unpublished_obj.project_id
        })
        resp = self.client.get(api_project_not_enrolled_state)
        self.assertEqual(resp.status_code, 404)

        #NOTE: Allowed!
        # #POST and make sure the user is enrolled
        # resp = self.client.post(api_project_lesson_not_enrolled_state)
        # self.assertEqual(resp.status_code, 403)
        # resp = self.client.get(api_project_lesson_not_enrolled_state)
        # self.assertEqual(resp.status_code, 404)
        #
        # #make sure the parent project state was automatically created
        # resp = self.client.get(api_project_not_enrolled_state)
        # self.assertEqual(resp.status_code, 404)

    # Permissions
    # ###########

    def test_user_only_sees_own_classroom_state(self):
        """
        Make sure that each user only sees their own state.
        """
        self.client.force_authenticate(self.global_user_1)
        data = self.client.get(self.api_classroom_detail_url, {'user': 'current'}).data
        self.assertTrue(data.get('enrolled'))

        not_enrolled_user = get_user_model().objects.annotate(
            classrooms_count=Count('classrooms_states'),
        ).filter(classrooms_count=0)[0]
        self.client.force_authenticate(not_enrolled_user)
        data = self.client.get(self.api_classroom_detail_url, {'user': 'current'}).data
        self.assertFalse(data.get('enrolled'))

    def test_user_only_sees_own_project_state(self):
        """
        Make sure that each user only sees their own state.
        """
        self.client.force_authenticate(self.global_user_1)
        data = self.client.get(self.api_project_detail_url, {'user': 'current'}).data
        self.assertTrue(data.get('enrolled'))

        not_enrolled_user = get_user_model().objects.annotate(
            projects_count=Count('projects'),
        ).filter(projects_count=0)[0]
        self.client.force_authenticate(not_enrolled_user)
        data = self.client.get(self.api_project_detail_url, {'user': 'current'}).data
        self.assertFalse(data.get('enrolled'))

    # Steps
    # #####

    def test_user_can_change_viewed_steps(self):
        """
        Make sure that a user that is enrolled to a lesson can complete steps.
        """

        lesson_with_steps = Lesson.objects.annotate(num_steps=Count('steps')).filter(num_steps__gt=3).order_by('-num_steps')[0]
        lesson_steps_ids = lesson_with_steps.steps.values_list('id', flat=True)
        LessonState.objects.get_or_create(  #enroll to lesson
            project_state=ProjectState.objects.get_or_create(user=self.global_user_1, project=lesson_with_steps.project)[0],
            lesson=lesson_with_steps
        )
        api_lesson_state_enrolled_url = reverse('api:project-lesson-state-detail',  kwargs={
            'project_pk': lesson_with_steps.project.id,
            'lesson_pk': lesson_with_steps.id
        })

        # Make sure the user is enrolled to this lesson.
        self.client.force_authenticate(self.global_user_1)
        resp = self.client.get(api_lesson_state_enrolled_url)
        self.assertEqual(resp.status_code, 200)

        def patch_steps(viewed_steps):
            resp = self.client.patch(api_lesson_state_enrolled_url, json.dumps({
                "viewedSteps": viewed_steps
            }), content_type='application/json')
            invalid_viewed_steps = set(viewed_steps) - set(lesson_steps_ids)
            if not invalid_viewed_steps:
                self.assertEqual(resp.status_code, 200)
                self.assertSetEqual(set(resp.data['viewedSteps']), set(lesson_with_steps.steps.filter(pk__in=resp.data['viewedSteps']).values_list('id', flat=True)))  #viewedSteps are all in lesson steps
                self.assertEqual(len(resp.data['viewedSteps']), len(set(viewed_steps)))  #viewedSteps has no duplicates
            else:
                self.assertEqual(resp.status_code, 400)
                self.assertIn('viewedSteps', resp.data)

        patch_steps([lesson_steps_ids[i] for i in [0,0,0]])
        patch_steps(lesson_steps_ids[:1] + [None])
        patch_steps(lesson_steps_ids[:1] + list(Step.objects.exclude(lesson=self.lesson_obj).values_list('id', flat=True)[:1]))
        patch_steps(lesson_steps_ids[0:max(1, len(lesson_steps_ids)-2)])
        patch_steps(lesson_steps_ids[0:max(1, len(lesson_steps_ids)):2])

    # users/:id/state/...
    # ###################

    def test_can_access_user_state_of_me_or_child_or_student(self):
        '''
        Check permissions to /users/:id/state/...
        '''
        def helper_check_access_with_user(user, me, classrooms_states_qs=None, projects_states_qs=None):
            # Log in with user
            self.client.force_authenticate(me)

            # Classroom State
            classrooms_states_qs = classrooms_states_qs if classrooms_states_qs else user.classrooms_states.all()
            resp = self.client.get(reverse('api:user-classroom-state-list', kwargs={
                'user_pk': user.id,
            }))
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.data['count'], classrooms_states_qs.count())
            for classroom_state in classrooms_states_qs.all():
                resp = self.client.get(reverse('api:user-classroom-state-detail', kwargs={
                    'user_pk': user.id,
                    'classroom_pk': classroom_state.classroom_id,
                }))
                self.assertEqual(resp.status_code, 200)

            # Project State
            projects_states_qs = projects_states_qs if projects_states_qs else user.projects.all()
            resp = self.client.get(reverse('api:user-project-state-list', kwargs={
                'user_pk': user.id,
            }))
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.data['count'], projects_states_qs.count())
            for project_state in projects_states_qs.all():
                resp1 = self.client.get(reverse('api:user-project-state-detail', kwargs={
                    'user_pk': user.id,
                    'project_pk': project_state.project_id,
                }))
                self.assertEqual(resp1.status_code, 200)

                # Project-Lesson State
                resp2 = self.client.get(reverse('api:user-project-lesson-state-list', kwargs={
                    'user_pk': user.id,
                    'project_pk': resp1.data['id'],
                }))
                self.assertEqual(resp2.status_code, 200)
                self.assertEqual(resp2.data['count'], project_state.lesson_states.count())

                for lesson_state in project_state.lesson_states.all():
                    resp3 = self.client.get(reverse('api:user-project-lesson-state-detail', kwargs={
                        'user_pk': user.id,
                        'project_pk': lesson_state.lesson.project.pk,
                        'lesson_pk': lesson_state.lesson.pk,
                    }))
                    self.assertEqual(resp3.status_code, 200)

        users = get_user_model().objects.all()
        superuser = users.filter(is_child=False).first()
        superuser.is_superuser = True
        superuser.save()
        for user in users:
            # self:
            helper_check_access_with_user(user, user)
            # moderator:
            moderator = user.guardians.first()
            if moderator:
                helper_check_access_with_user(user, moderator)
            # teacher:
            classroom_state = user.classrooms_states.exclude(classroom__owner=F('user__guardians')).first()
            if classroom_state:
                teacher = classroom_state.classroom.owner
                helper_check_access_with_user(user, teacher,
                                              #filter classrooms and projects states for the teacher:
                                              user.classrooms_states.filter(classroom__owner=teacher),
                                              user.projects.filter(project__in=ProjectInClassroom.objects.filter(classroom__owner=teacher).values('project'))
                )
            # super user:
            helper_check_access_with_user(user, superuser)

        # Cleanup
        superuser.is_staff = False
        superuser.save()

    def test_can_access_user_state_of_student(self):
        '''
        Check teacher can get student states.
        '''
        student = get_user_model().objects.filter(classrooms_states__isnull=False).exclude(classrooms_states__classroom__owner=F('guardians')).first()
        teacher = student.classrooms_states.first().classroom.owner
        self.client.force_authenticate(teacher)

        resp = self.client.get(
            reverse('api:user-classroom-state-list', kwargs={
                'user_pk': student.pk,
            })
        )
        self.assertEqual(resp.status_code, 200)
        classrooms_ids = [x['id'] for x in resp.data['results']]
        for classroom_state in student.classrooms_states.all():
            resp2 = self.client.get(
                reverse('api:user-classroom-state-detail', kwargs={
                    'classroom_pk': classroom_state.classroom.pk,
                    'user_pk': student.pk,
                })
            )
            if classroom_state.classroom.owner == teacher:
                self.assertIn(classroom_state.classroom.id, classrooms_ids)
                self.assertEqual(resp2.status_code, 200)
            else:
                self.assertNotIn(classroom_state.classroom.id, classrooms_ids)
                self.assertEqual(resp2.status_code, 403)

    def test_cant_access_user_state_not_of_me_or_child_or_teacher(self):
        '''
        Check permissions to /users/:id/state/...
        '''
        users = get_user_model().objects.all()

        for user in users:

            # Log in with a user who's not the 'user' and not her guardian.
            me = next(
                u 
                for u 
                in users 
                if (
                    u.id != user.id and
                    (u.id not in user.guardians.all().values_list('id', flat=True)) and
                    (not user.classrooms_states.filter(classroom__in=u.authored_classrooms.all()).exists())  #not student of teacher
                )
            )
            self.client.force_authenticate(me)

            # Classroom State
            resp = self.client.get(reverse('api:user-classroom-state-list', kwargs={
                'user_pk': user.id,
            }))
            self.assertEqual(resp.status_code, 403)
            for classroom_state in user.classrooms_states.all():
                resp = self.client.get(reverse('api:user-classroom-state-detail', kwargs={
                    'user_pk': user.id,
                    'classroom_pk': classroom_state.classroom_id,
                }))
                self.assertEqual(resp.status_code, 403)

            # Project State
            resp = self.client.get(reverse('api:user-project-state-list', kwargs={
                'user_pk': user.id,
            }))
            self.assertEqual(resp.status_code, 403)
            for project_state in user.projects.all():
                resp = self.client.get(reverse('api:user-project-state-detail', kwargs={
                    'user_pk': user.id,
                    'project_pk': project_state.project_id,
                }))
                self.assertEqual(resp.status_code, 403)

                # Project-Lesson State
                resp = self.client.get(reverse('api:user-project-lesson-state-list', kwargs={
                    'user_pk': user.id,
                    'project_pk': project_state.project_id,
                }))
                self.assertEqual(resp.status_code, 403)

                for lesson_state in project_state.lesson_states.all():
                    resp = self.client.get(reverse('api:user-project-lesson-state-detail', kwargs={
                        'user_pk': user.id,
                        'project_pk': lesson_state.lesson.project.pk,
                        'lesson_pk': lesson_state.lesson.pk,
                    }))
                    self.assertEqual(resp.status_code, 403)

    def test_user_classroom_state_is_same_as_classroom_state(self):
        '''
        Check that /users/:id/state/classrooms/:id/ returns the exact same result
        as /classrooms/:id/state/ when the correct user is logged in.
        '''

        users = get_user_model().objects.annotate(
            classrooms_count=Count('classrooms_states'),
        ).filter(
            classrooms_count__gte=1,
        )

        for me in users:
            self.client.force_authenticate(me)

            for classroom_state in me.classrooms_states.all():
                resp1 = self.client.get(reverse('api:user-classroom-state-detail', kwargs={
                    'user_pk': me.id,
                    'classroom_pk': classroom_state.classroom_id,
                }))

                resp2 = self.client.get(reverse('api:classroom-state-detail', kwargs={
                    'classroom_pk': classroom_state.classroom_id
                }))

                self.assertEqual(resp1.status_code, 200)
                self.assertEqual(resp2.status_code, 200)

                self.assertEqual(resp1.data, resp2.data)

    def test_user_project_state_is_same_as_project_state(self):
        '''
        Check that /users/:id/state/projects/:id/ returns the exact same result
        as /projects/:id/state/ when the correct user is logged in.
        '''

        users = get_user_model().objects.annotate(
            projects_count=Count('projects'),
        ).filter(
            projects_count__gte=1,
        )

        for me in users:
            self.client.force_authenticate(me)

            for project_state in me.projects.all():
                resp1 = self.client.get(reverse('api:user-project-state-detail', kwargs={
                    'user_pk': me.id,
                    'project_pk': project_state.project_id,
                }))

                resp2 = self.client.get(reverse('api:project-state-detail', kwargs={
                    'project_pk': project_state.project_id
                }))

                self.assertEqual(resp1.status_code, 200)
                self.assertEqual(resp2.status_code, 200)

                self.assertEqual(resp1.data, resp2.data)

    def test_user_lesson_state_is_same_as_lesson_state(self):
        '''
        Check that /users/:id/state/lessons/:id/ returns the exact same result
        as /lessons/:id/state/ when the correct user is logged in.
        '''
        
        users = get_user_model().objects.annotate(
            lessons_count=Count('projects__lesson_states'),
        ).filter(
            lessons_count__gte=1,
        )

        for me in users:
            self.client.force_authenticate(me)

            lesson_states = LessonState.objects.all().filter(project_state__user=me)
            for lesson_state in lesson_states:
                resp1 = self.client.get(reverse('api:user-project-lesson-state-detail', kwargs={
                    'user_pk': me.id,
                    'lesson_pk': lesson_state.lesson_id,
                    'project_pk': lesson_state.lesson.project_id,
                }))

                resp2 = self.client.get(reverse('api:project-lesson-state-detail', kwargs={
                    'project_pk': lesson_state.lesson.project_id,
                    'lesson_pk': lesson_state.lesson.id,
                }))

                self.assertEqual(resp1.status_code, 200)
                self.assertEqual(resp2.status_code, 200)

                self.assertEqual(resp1.data, resp2.data)

    def test_user_classroom_project_state_is_same_as_user_project_state(self):
        '''
        Check that /users/:id/state/classrooms/:id/projects/:id/ returns the exact same result
        as /users/:id/state/projects/:id/ when the correct user is logged in.
        '''

        users = get_user_model().objects.annotate(
            classrooms_count=Count('classrooms_states'),
        ).filter(
            classrooms_count__gte=1,
        )

        for me in users:
            self.client.force_authenticate(me)

            classrooms_states = ClassroomState.objects.all().filter(user=me)
            for classroom_state in classrooms_states:
                classroom_projects_states = classroom_state.get_projects_states()
                classroom_projects_states_projectids = [x.project_id for x in classroom_projects_states]
                for project in classroom_state.classroom.projects.all():
                    resp1 = self.client.get(reverse('api:user-classroom-project-state-detail', kwargs={
                        'user_pk': me.id,
                        'project_pk': project.id,
                        'classroom_pk': classroom_state.classroom_id,
                    }))

                    resp2 = self.client.get(reverse('api:user-project-state-detail', kwargs={
                        'user_pk': me.id,
                        'project_pk': project.id,
                    }))

                    if project.id in classroom_projects_states_projectids:
                        self.assertEqual(resp1.status_code, 200)
                        self.assertEqual(resp2.status_code, 200)

                        self.assertEqual(resp1.data, resp2.data)

                    else:
                        self.assertEqual(resp1.status_code, 404)
                        self.assertEqual(resp2.status_code, 404)

    def test_user_classroom_states_filtering(self):
        '''
        Tests some filters of /users/:id/classrooms/state/.
        '''

        user = get_user_model().objects.annotate(
            classrooms_count=Count('classrooms_states'),
        ).filter(
            classrooms_count__gte=2,
        ).first()
        self.client.force_authenticate(user)

        user_classroom_state = user.classrooms_states.first()
        filters = [
            (
                {'studentStatus': 'approved'},
                {'status': 'approved'}
            ),
            (
                {'studentStatus__in': 'approved,pending'},
                {'status__in': ['approved', 'pending']}
            ),
            (
                {'studentClassroom': user_classroom_state.classroom.id},
                {'classroom': user_classroom_state.classroom.id}
            ),
            (
                {'studentClassroom__author__id': user_classroom_state.classroom.owner_id},
                {'classroom__owner_id': user_classroom_state.classroom.owner_id}
            ),
        ]

        for api_filters, db_filters in filters:
            db_filters = db_filters if db_filters is not None else api_filters
            objs_from_db = user.classrooms_states.filter(**db_filters)

            resp = self.client.get(reverse('api:user-classroom-state-list', kwargs={'user_pk': user.id}), dict(
                api_filters.items() + {'pageSize': objs_from_db.count()}.items()
            ))
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.data['count'], objs_from_db.count(), msg=str(api_filters))
            self.assertSetEqual(set([x['id'] for x in resp.data['results']]), set([x.classroom_id for x in objs_from_db]))

    def test_user_project_states_of_deleted_unpublished_project_are_not_shown(self):
        '''
        Tests that /users/:id/state/projects/:id/ does not show states of deleted unpublished project.
        '''
        me = get_user_model().objects.annotate(
            projects_count=Count('projects'),
        ).filter(
            projects__project__publish_mode=Project.PUBLISH_MODE_PUBLISHED,
            projects_count__gte=2,
        )[0]
        my_projects_count = me.projects.count()

        self.client.force_authenticate(me)

        # Total project states of the user:
        resp = self.client.get(reverse('api:user-project-state-list', kwargs={
            'user_pk': me.id,
        }))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], my_projects_count)

        project_state_published, project_state_unpublished = me.projects.all()[:2]

        # Project state of published project deleted:
        project_state_published.project.delete()

        resp1 = self.client.get(reverse('api:user-project-state-detail', kwargs={
            'user_pk': me.id,
            'project_pk': project_state_published.project_id,
        }))
        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(me.projects.filter(pk=project_state_published.pk).count(), 1)

        # Project state of unpublished project deleted:
        project_state_unpublished.project.publish_mode = Project.PUBLISH_MODE_EDIT
        project_state_unpublished.project.save()
        project_state_unpublished.project.delete()

        resp1 = self.client.get(reverse('api:user-project-state-detail', kwargs={
            'user_pk': me.id,
            'project_pk': project_state_unpublished.project_id,
        }))
        self.assertEqual(resp1.status_code, 404)
        self.assertEqual(me.projects.filter(pk=project_state_unpublished.pk).count(), 0)

        # Check again total states of the user:
        resp = self.client.get(reverse('api:user-project-state-list', kwargs={
            'user_pk': me.id,
        }))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], my_projects_count-1)

        # Reset
        project_state_published.is_deleted = False


    # Lesson/Project Completion status
    # ################################

    def test_project_is_completed_false_on_init(self):

        self.client.force_authenticate(self.global_user_1)

        project_pk = Project.objects.exclude(
            id__in=ProjectState.objects.filter(
                user=self.global_user_1
            ).values_list('id', flat=True)
        ).first().pk
        url = reverse('api:project-state-detail',  kwargs={'project_pk': project_pk})
        resp = self.client.post(url)

        self.assertIn(resp.status_code, xrange(200, 202))
        self.assertFalse(resp.data['isCompleted'])

    def test_project_is_completed_is_read_only(self):

        self.client.force_authenticate(self.global_user_1)
        project_pk = ProjectState.objects.filter(
            user=self.global_user_1
        ).first().project_id
        url = reverse('api:project-state-detail',  kwargs={'project_pk': project_pk})
        resp = self.client.patch(url, json.dumps({
            'isCompleted': True
        }), content_type='application/json')

        self.assertFalse(ProjectState.objects.get(
            user=self.global_user_1, project_id=project_pk
        ).is_completed)

    def test_lesson_is_completed_is_writable(self):

        self.client.force_authenticate(self.global_user_1)

        lesson = LessonState.objects.filter(
            project_state__user=self.global_user_1
        ).first().lesson
        url = reverse('api:project-lesson-state-detail',  kwargs={'project_pk': lesson.project.pk, 'lesson_pk': lesson.pk})
        resp = self.client.patch(url, json.dumps({
            'isCompleted': True
        }), content_type='application/json')

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(LessonState.objects.get(
            project_state__user=self.global_user_1, lesson_id=lesson.pk
        ).is_completed)

    def test_when_last_lesson_turned_completed_project_state_also_completed(self):
        '''
        If all of the lessons except for one are completed, when the last lesson
        is marked as completed, the ProjectState will also change to completed.
        '''
        
        self.client.force_authenticate(self.global_user_1)

        ps = ProjectState.objects \
            .select_related('project').prefetch_related('project__lessons') \
            .filter(user=self.global_user_1).first()

        ls_list = []

        # Make all of the LessonStates except for the first one completed.
        # Make the first lesson and the project state incomplete.
        for idx, lesson in enumerate(ps.project.lessons.all()):

            ls, created = LessonState.objects.update_or_create(
                project_state=ps,
                lesson=lesson,
                defaults={
                    'is_completed': (idx != 0),
                },
            )

            ls_list.append(ls)

        ps.is_completed = False
        ps.save()

        lesson = ls_list[0].lesson
        resp = self.client.patch(
            reverse('api:project-lesson-state-detail',  kwargs={'project_pk': lesson.project.pk, 'lesson_pk': lesson.pk}),
            json.dumps({
                'isCompleted': True
            }),
            content_type='application/json'
        )

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(ProjectState.objects.get(pk=ps.pk).is_completed)
        

    def test_project_state_changed_to_non_completed_when_lessons_get_uncompleted(self):
        '''
        If all of the lessons are marked as completed and the ProjectState as well.
        When one of the lessons will be marked uncompleted, then the ProjectState will
        change back as well.
        '''
        
        self.client.force_authenticate(self.global_user_1)

        #Note: make sure that project has at least 1 lesson that is not stepless.
        project = Project.objects.annotate(num_lessons=Count('lessons')).filter(num_lessons__gte=1).first()
        lesson_with_steps = project.lessons.create(
            title='Lesson with steps',
            application=next(app for app,_ in Lesson.APPLICATIONS if app not in Lesson.STEPLESS_APPS),
            order=0,
        )
        ps, _ = ProjectState.objects.get_or_create(
            project=project,
            user=self.global_user_1,
        )

        # Make all of the LessonStates completed.
        for idx, lesson in enumerate(ps.project.lessons.all()):
            LessonState.objects.update_or_create(
                project_state=ps,
                lesson=lesson,
                defaults={
                    'is_completed': True,
                },
            )

        # Mark the ProjectState completed.
        ps.is_completed = True
        ps.save()

        resp = self.client.patch(
            reverse('api:project-lesson-state-detail',  kwargs={'project_pk': lesson_with_steps.project.pk, 'lesson_pk': lesson_with_steps.pk}),
            json.dumps({
                'isCompleted': False
            }),
            content_type='application/json'
        )

        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['isCompleted'])
        self.assertFalse(ProjectState.objects.get(pk=ps.pk).is_completed)

    def test_on_lesson_state_change_project_state_doesnt_change_if_not_all_lessons_completed(self):
        '''
        If LessonState changes to completed but not all of the LessonStates are 
        completed, then the ProjectState shouldn't change to is_completed.
        '''
        
        self.client.force_authenticate(self.global_user_1)

        ps = ProjectState.objects \
            .select_related('project').prefetch_related('project__lessons') \
            .annotate(lessons_count=Count('project__lessons')) \
            .filter(user=self.global_user_1, lessons_count__gte=2) \
            .first()

        ls_list = []
        
        # Make all of the LessonStates not completed.
        for idx, lesson in enumerate(ps.project.lessons.all()):

            ls, created = LessonState.objects.get_or_create(
                project_state=ps,
                lesson=lesson,
                defaults={
                    'is_completed': False,
                },
            )

            ls_list.append(ls)

        # Mark the ProjectState not completed.
        ps.is_completed = False
        ps.save()

        lesson = ls_list[0].lesson
        resp = self.client.patch(
            reverse('api:project-lesson-state-detail',  kwargs={'project_pk': lesson.project.pk, 'lesson_pk': lesson.pk}),
            json.dumps({
                'isCompleted': True
            }),
            content_type='application/json'
        )

        self.assertEqual(resp.status_code, 200)
        self.assertFalse(ProjectState.objects.get(pk=ps.pk).is_completed)

    def test_project_state_doesnt_change_if_some_lesson_states_missing(self):
        '''
        If LessonState changes to completed and all of the lesson states are 
        completed, but some lesson states are missing, then the ProjectState 
        shouldn't change to is_completed.
        '''

        self.client.force_authenticate(self.global_user_1)

        ps = ProjectState.objects \
            .select_related('project').prefetch_related('project__lessons') \
            .annotate(lessons_count=Count('project__lessons')) \
            .filter(user=self.global_user_1, lessons_count__gte=2) \
            .first()

        # Delete all of the lesson states.
        ps.lesson_states.all().delete()

        # Create one lesson state that's not completed.
        ls = LessonState.objects.create(
            project_state=ps,
            lesson=ps.project.lessons.first(),
            is_completed=False,
        )

        # Mark the ProjectState not completed.
        ps.is_completed = False
        ps.save()

        # Make that lesson state completed:
        lesson = ls.lesson
        resp = self.client.patch(
            reverse('api:project-lesson-state-detail',  kwargs={'project_pk': lesson.project.pk, 'lesson_pk': lesson.pk}),
            json.dumps({
                'isCompleted': True
            }),
            content_type='application/json'
        )

        self.assertEqual(resp.status_code, 200)
        self.assertFalse(ProjectState.objects.get(pk=ps.pk).is_completed)

    def test_project_state_change_if_deleting_complete_lesson_state(self):
        '''
        If ProjectState is completed with all its lesson states completed,
        and a lesson state is deleted, then ProjectState should change to
        not completed.
        '''

        self.client.force_authenticate(self.global_user_1)

        ps = ProjectState.objects \
            .select_related('project').prefetch_related('project__lessons') \
            .annotate(lessons_count=Count('project__lessons')) \
            .filter(user=self.global_user_1, lessons_count__gte=2) \
            .first()

        ls_list = []

        # Make all of the LessonStates not completed.
        for idx, lesson in enumerate(ps.project.lessons.all()):

            ls, created = LessonState.objects.get_or_create(
                project_state=ps,
                lesson=lesson,
                defaults={
                    'is_completed': True,
                },
            )

            ls_list.append(ls)

        # Mark the ProjectState completed.
        ps.is_completed = True
        ps.save()

        # Delete a lesson state:
        lesson = ls_list[0].lesson
        resp = self.client.delete(
            reverse('api:project-lesson-state-detail',  kwargs={'project_pk': lesson.project.pk, 'lesson_pk': lesson.pk}),
        )

        self.assertEqual(resp.status_code, 204)
        self.assertFalse(ProjectState.objects.get(pk=ps.pk).is_completed)


    # Lesson Canvas Document ID
    # #########################

    def test_lesson_state_canvas_document_id(self):
        #get unpublished project with some lessons and pick a lesson:
        lesson_application = settings.LESSON_APPS['Tinkercad']['db_name']
        parent_project_obj = Project.objects.filter(
            lessons__application=lesson_application,
        ).annotate(
            num_lessons=Count('lessons')
        ).filter(
            publish_mode=Project.PUBLISH_MODE_EDIT,
            owner=self.global_user_1,
            num_lessons__gte=2,
        ).order_by('-num_lessons')[0]
        self.assertGreaterEqual(parent_project_obj.num_lessons, 2, msg='Make sure to pick a project that contains at least 2 lessons of %s' % lesson_application)
        lesson1, lesson2 = parent_project_obj.lessons.filter(application=lesson_application)[:2]

        user = self.global_user_2
        project_state, _ = parent_project_obj.registrations.get_or_create(user=user)

        def _helper_check_lessons_states_canvas_and_params(init_canvas_id):
            lesson1.registrations.filter(user=user).delete()
            lesson2.registrations.filter(user=user).delete()

            lesson1_state = lesson1.registrations.create(project_state=project_state, user=user)
            self.assertTupleEqual(lesson1_state.get_canvas_document_id(), (init_canvas_id, True))
            lesson1_state = LessonState.objects.get(pk=lesson1_state.pk)
            self.assertIsNone(lesson1_state.extra)
            self.assertDictEqual(lesson1_state.get_canvas_external_params(), {
                'edu-document-id': init_canvas_id,
                'edu-document-copy': 'true',
            } if init_canvas_id is not None else {})

            lesson2_state = lesson2.registrations.create(project_state=project_state, user=user)
            self.assertTupleEqual(lesson2_state.get_canvas_document_id(), (init_canvas_id, True))
            lesson2_state = LessonState.objects.get(pk=lesson2_state.pk)
            self.assertIsNone(lesson2_state.extra)
            self.assertDictEqual(lesson2_state.get_canvas_external_params(), {
                'edu-document-id': init_canvas_id,
                'edu-document-copy': 'true',
            } if init_canvas_id is not None else {})

            #set user personal canvas id in state for lesson2:
            user_canvas_id = 'MyCanvas-2'
            lesson2_state.extra = {
                'canvasDocumentId': user_canvas_id,
            }
            lesson2_state.save()
            self.assertTupleEqual(lesson2_state.get_canvas_document_id(), (user_canvas_id, False))
            self.assertDictEqual(lesson2_state.get_canvas_external_params(), {
                'edu-document-id': user_canvas_id,
            })

            self.assertTupleEqual(lesson1_state.get_canvas_document_id(), (user_canvas_id, False))
            lesson1_state = LessonState.objects.get(pk=lesson1_state.pk)
            self.assertEqual(lesson1_state.extra['canvasDocumentId'], user_canvas_id)
            self.assertDictEqual(lesson1_state.get_canvas_external_params(), {
                'edu-document-id': user_canvas_id,
            })

        # With initCanvasId
        init_canvas_id = 'A1B2C3'
        parent_project_obj.extra = parent_project_obj.validate_extra_field({
            'lessonsInit': [{
                'lessonsIds': [lesson1.id, lesson2.id],
                'initCanvasId': init_canvas_id,
            },]
        })
        parent_project_obj.save()
        _helper_check_lessons_states_canvas_and_params(init_canvas_id)

        # Without initCanvasId
        parent_project_obj.extra = parent_project_obj.validate_extra_field({
            'lessonsInit': [{
                'lessonsIds': [lesson1.id, lesson2.id],
            },]
        })
        parent_project_obj.save()
        _helper_check_lessons_states_canvas_and_params(None)
