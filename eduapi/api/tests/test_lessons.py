import re
import unittest
from itertools import izip

from django.db.models import Count, Q
from django.core.urlresolvers import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.urlresolvers import NoReverseMatch
from django.core import management

from rest_framework.test import APITestCase as DRFTestCase
from rest_framework import status

from edu_api_test_case import EduApiTestCase
from ..serializers import LessonSerializer

from ..models import (
    Lesson,
    Project,
)

class LessonTests(EduApiTestCase, DRFTestCase):
    '''
    Tests the Lesson API.
    '''

    fixtures = ['test_projects_fixture_1.json']
    model = Lesson

    def api_test_init(self):
        super(LessonTests, self).api_test_init()

        self.actions = ['list', 'retrieve']  #allowed actions for this test
        self.global_user = get_user_model().objects.filter(id=2)
        self.api_list_url = reverse('api:lesson-list')
        self.api_details_url = 'api:lesson-detail'
        self.non_existant_obj_details_url = reverse(self.api_details_url, kwargs={'pk': 4444})
        self.all_user_objects = Lesson.objects.origins().filter(
            Q(project__publish_mode=Project.PUBLISH_MODE_PUBLISHED)  #part of a published project
            | Q(project__owner=self.global_user) | Q(project__owner__in=self.global_user[0].delegators.all()) | Q(project__owner__in=self.global_user[0].children.all())  #owner / delegate / guardian
            | Q(application__in=[g.name for g in self.global_user[0].groups.all()]),  #application lesson
            Q(project__lock=Project.NO_LOCK)
        ).order_by('id')
        self.all_public_objects = Lesson.objects.origins().filter(
            project__publish_mode=Project.PUBLISH_MODE_PUBLISHED,
        ).order_by('id')
        self.serializer = LessonSerializer
        self.sort_key = 'id'
        self.fields = tuple([fn for fn in self.serializer.Meta.fields if fn not in ('applicationBlob',)])
        self.filters = [
            ({'idList': '2,3,a,,,15'}, 'ERROR',),
            ({'idList': '2'}, {'id__in': [2]},),
            ({'idList': 'a,b'}, 'ERROR',),
            ({'idList': ''}, 'ERROR',),
            ({'numberOfSteps__gt': 1}, {'steps_count__gt': 1}),
            ({'numberOfStudents__gte': 1}, {'students_count__gte': 1}),
            ({'publishMode': 'published'}, {'project__publish_mode__in': ['published']}),
            ({'publishMode': 'review,ready'}, {'project__publish_mode__in': ['review', 'ready']}),
            ({'publishMode': 'edit,  ,,  ,, review,,ready  ,, '}, 'ERROR'),
        ]
        self.pagination = True
        self.project = Project.objects.filter(owner=self.global_user, publish_mode=Project.PUBLISH_MODE_EDIT).first()

    def setUp(self):
        super(LessonTests, self).setUp()

    def get_api_details_url(self, obj):
        return reverse(self.api_details_url, kwargs={
            'pk': obj.id
        })


    def test_get_unpublished_lesson_as_provider(self):
        #get user that is not project owner:
        user1, user2 = get_user_model().objects.exclude(
            Q(pk=self.global_user.pk) |
            Q(pk__in=self.global_user.guardians.all()) |
            Q(pk__in=self.global_user.delegates.all()) |
            Q(groups__name='123dcircuits')
        )[:2]

        #add user2 to '123dcircuits' group:
        # this assumes there's a circuits group in the database (was added in migration)
        group = Group.objects.get(name='123dcircuits')
        group.user_set.add(user2)

        #get published lessons count for each user
        for user in [user1, user2]:
            self.client.force_authenticate(user)
            # get published lessons
            response = self.client.get(self.api_list_url)
            # validate response
            if user == user2:
                self.assertEqual(response.status_code, status.HTTP_200_OK)
            if response.status_code == status.HTTP_200_OK:
                # keep count of published lessons
                user.published_lesson_count =  response.data['count']
            elif response.status_code == status.HTTP_404_NOT_FOUND:
                # not allowed
                user.published_lesson_count = None
            else:
                self.fail('Returned unexpected status code: %s.' %response.status_code)

        # add unpublished lesson by another user
        lesson = Lesson.objects.create(
            title='Unpublished lesson',
            application='123dcircuits',
            project=self.project,
            order=self.project.lessons.count(),
        )

        if user1.published_lesson_count is not None:
            self.client.force_authenticate(user1)
            # get all published lessons
            response = self.client.get(self.api_list_url)
            # validate response
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            # verify new unpublished lesson is not included
            self.assertEqual(response.data['count'], user1.published_lesson_count)

        self.client.force_authenticate(user2)
        # as provider - get all lessons
        response = self.client.get(self.api_list_url)
        # validate response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # verify new unpublished lesson is not included
        self.assertEqual(response.data['count'], user2.published_lesson_count + 1)

        # Cleanup
        group.user_set.remove(user2)

    def test_app_cant_get_unpublished_lessons_of_other_apps(self):

        groups = Group.objects.filter(name__in=[a for a,_ in Lesson.APPLICATIONS])

        # Check that there are groups in the database.
        self.assertGreaterEqual(len(groups), 1)

        for group in groups:

            user = get_user_model().objects.create(
                oxygen_id='923423490234',
                member_id='923423490234',
                email='t@asdfssafsa.com',
            )
            user.groups.add(group)

            self.client.force_authenticate(user)

            # Get a lesson that:
            #   1. Doesn't belong to this user - easy, the user didn't create any lessons.
            #   2. Is not published.
            #   3. belongs to another application.
            other_app_lesson = Lesson.objects.origins().filter(
                project__publish_mode=Project.PUBLISH_MODE_EDIT
            ).exclude(
                application=group.name
            ).first()
            app_project = other_app_lesson.project
            self.assertEqual(app_project.publish_mode, Project.PUBLISH_MODE_EDIT)

            # Check that the lesson is not accessible by the user.
            resp = self.client.get(self.get_api_details_url(other_app_lesson))
            self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

            # Delete the user from the Database.
            user.delete()

    def test_embedded_steps_in_lesson(self):
        '''
        Checks that the embedded steps in the Lesson are by their order and
        are true to the DB.
        '''

        # Get a lesson with at least 3 steps.
        lesson = self.all_user_objects.annotate(
            steps_num=Count('steps')
        ).filter(steps_num__gte=3)[0]

        api_lesson = self.client.get(
            self.get_api_details_url(lesson),
            {'embed': 'steps'}
        ).data

        self.assertGreaterEqual(len(api_lesson['steps']), 3)

        db_steps = lesson.steps.all().order_by('order')
        self.assertEqual(len(db_steps), len(api_lesson['steps']))

        # Make sure that each step in the lesson, is true to the DB.
        for db_step, api_step in izip(db_steps, api_lesson['steps']):

            self.assertEqual(db_step.order, api_step['order'])
            self.assertEqual(db_step.id, api_step['id'])

    def test_steps_urls_in_lesson(self):
        '''
        Checks that the steps URLs in the Lesson object really return the steps
        when they're used.
        '''

        url_to_order = lambda url: int(re.search(r'/([0-9]+)/$', url).group(1))

        # Get a lesson with at least 3 steps.
        lesson = self.all_user_objects.all().annotate(
            steps_num=Count('steps')
        ).filter(steps_num__gte=3)[0]

        api_lesson = self.client.get(self.get_api_details_url(lesson), {'embed': 'steps'}).data
        self.assertGreaterEqual(len(api_lesson['steps']), 3)

        # Make sure that each step's URL in the lesson, returns the appropriate step.
        for idx, step in enumerate(api_lesson['steps']):
            step_url = step.get('self')
            step = self.client.get(step_url).data
            self.assertRegexpMatches(step_url, r'/steps/' + str(step['order']) + '/$')

            # Make sure that the order is correct
            if idx + 1 < len(api_lesson['steps']):
                self.assertLess(
                    url_to_order(step_url),
                    url_to_order(api_lesson['steps'][idx + 1]['self'])
                )


    def test_lesson_counters(self):
        """
        Make sure the lesson state counters are correct.
        """
        #build counters:
        management.call_command('rebuild_counters')

        self.client.force_authenticate(self.global_user)
        data = self.client.get(self.api_list_url).data['results']

        for lesson_data in data:
            lesson_obj = Lesson.objects.get(id=lesson_data['id'])
            self.assertEqual(lesson_data['numberOfSteps'], lesson_obj.steps.count())
            self.assertEqual(lesson_data['numberOfStudents'], lesson_obj.registrations.count())


    def test_lessons_list_non_searchable(self):
        user = self.global_user
        user_all_lessons = self.all_user_objects
        self.assertEqual(user_all_lessons.count(), user_all_lessons.filter(project__is_searchable=True).count(), msg='Assumed starting when all projects are searchable.')
        self.client.force_authenticate(user)

        num_user_all_lessons = user_all_lessons.count()

        resp = self.client.get(self.api_list_url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], num_user_all_lessons)

        # Hide project of user and project not of user
        hidden_project_1 = user.authored_projects.annotate(num_lessons=Count('lessons')).filter(num_lessons__gt=1, is_searchable=True)[0]
        hidden_project_1.is_searchable = False
        hidden_project_1.save()
        hidden_project_2 = Project.objects.exclude(owner=user).annotate(num_lessons=Count('lessons')).filter(num_lessons__gt=1, is_searchable=True)[0]
        hidden_project_2.is_searchable = False
        hidden_project_2.save()

        # Get projects default list
        user_all_lessons_default_list = user_all_lessons.filter(
            (Q(project__owner=user) | Q(project__owner__in=user.delegators.all()) | Q(project__owner__in=user.children.all())) |
            Q(project__is_searchable=True)
        )
        num_user_all_lessons_default_list = user_all_lessons_default_list.count()
        # make sure that lessons of the hidden project that is not of the user are not in the default list:
        self.assertEqual(num_user_all_lessons_default_list, num_user_all_lessons-hidden_project_2.num_lessons)
        self.assertSequenceEqual(
            set([x.id for x in user_all_lessons_default_list]),
            set([x.id for x in user_all_lessons if x.project_id != hidden_project_2.id])
        )

        # GET /lessons/
        resp = self.client.get(self.api_list_url, {'pageSize': num_user_all_lessons})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], user_all_lessons_default_list.count())
        self.assertSetEqual(
            set([x['id'] for x in resp.data['results']]),
            set([x.id for x in user_all_lessons_default_list])
        )

    def test_lesson_detail_non_searchable(self):
        user = self.global_user
        self.client.force_authenticate(user)

        # Get project, hide it, and check that it is still accessible explicitly for details:
        hidden_project = Project.objects.exclude(owner=user).filter(is_searchable=True).annotate(num_lessons=Count('lessons')).filter(num_lessons__gt=1)[0]
        hidden_lesson = hidden_project.lessons.all()[0]

        resp = self.client.get(self.get_api_details_url(hidden_lesson))
        self.assertEqual(resp.status_code, 200)

        hidden_project.is_searchable = False
        hidden_project.save()
        resp = self.client.get(self.get_api_details_url(hidden_lesson))
        self.assertEqual(resp.status_code, 200)
