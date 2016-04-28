import copy
import json
import threading
import unittest

from django.conf import settings
from api.tests import test_lessons
from django.core.urlresolvers import reverse
from django.contrib.auth import get_user_model
from django.db.models import Count, Max, Q
from django.contrib.auth.models import Group
from django.core.serializers.json import DjangoJSONEncoder

from rest_framework import status

from ..serializers import LessonSerializer
from ..models import Lesson, Project


class LessonsInProjectsTests(test_lessons.LessonTests):

    fixtures = ['test_projects_fixture_1.json']

    def api_test_init(self):
        super(LessonsInProjectsTests, self).api_test_init()

        delattr(self, 'actions')  #use default - all actions

        self.put_actions = []
        self.VIDEO_APP = settings.LESSON_APPS['Video']['db_name']
        self.project = Project.objects.filter(owner=self.global_user, publish_mode=Project.PUBLISH_MODE_EDIT).annotate(num_lessons=Count('lessons')).order_by('-num_lessons').first()
        self.project_published = Project.objects.filter(publish_mode=Project.PUBLISH_MODE_PUBLISHED).annotate(num_lessons=Count('lessons')).order_by('-num_lessons').first()

        self.put_actions = [
            # Successful PUT
            {
                'get_object': lambda: Lesson.objects.exclude(title='1111111').filter(project__publish_mode=Project.PUBLISH_MODE_EDIT, project__owner=self.global_user).first(),
                'updated_data': {'title': '1111111'},
            },
            {
                'get_object': lambda: Lesson.objects.filter(project__publish_mode=Project.PUBLISH_MODE_EDIT, application=self.VIDEO_APP).first(),
                'updated_data': {
                    'applicationBlob': {},
                },
            },
            {
                'get_object': lambda: Lesson.objects.filter(project__publish_mode=Project.PUBLISH_MODE_EDIT, application=self.VIDEO_APP).first(),
                'updated_data': {
                    'applicationBlob': {'video': None},
                },
            },
            {
                'get_object': lambda: Lesson.objects.filter(application=self.VIDEO_APP, project__publish_mode=Project.PUBLISH_MODE_EDIT, project__owner=self.global_user).first(),
                'updated_data': {
                    'applicationBlob': {'video': {'vendor': 'youtube', 'id': '1234567890a', 'meta': {'published': '2012-06-14T23:28:03.000Z', 'title': 'Youtube Video', 'author': 'Youtube Author', 'duration': 'PT15M33S'}}},
                },
            },
            # # Can't edit published lesson
            # This test fails, need to uncomment and fix API.
            # {
            #     'get_object': lambda: Project.objects.filter(project__publish_mode=Project.PUBLISH_MODE_PUBLISHED,owner=self.global_user).first().lessons.first(),
            #     'updated_data': {'title': '1111111'},
            #     'expected_result': 400,
            # },
            # Empty title
            {
                'get_object': lambda: Lesson.objects.filter(project__publish_mode=Project.PUBLISH_MODE_EDIT, project__owner=self.global_user).first(),
                'updated_data': {'title': ''},
                'expected_result': 400,
                'expected_response': {"title": ["This field may not be blank."]},
            },
            # Not Authorized
            {
                'user': get_user_model().objects.get(id=4),
                'get_object': lambda: Lesson.objects.filter(project__publish_mode=Project.PUBLISH_MODE_PUBLISHED).exclude(project__owner_id=4)[0],
                'expected_result': 403,
            },
            # Not Authenticated
            {
                'user': None,
                'get_object': lambda: Lesson.objects.filter(project__publish_mode=Project.PUBLISH_MODE_PUBLISHED)[0],
                'expected_result': 401,
            },
            # Not valid video applicationBlob
            {
                'get_object': lambda: Lesson.objects.filter(application=self.VIDEO_APP, project__publish_mode=Project.PUBLISH_MODE_EDIT, project__owner=self.global_user).first(),
                'updated_data': {
                    'applicationBlob': {'video': {'vendor': 'Unknown', 'id': '1234567890a'}},
                },
                'expected_result': 400,
            },
            {
                'get_object': lambda: Lesson.objects.filter(application=self.VIDEO_APP, project__publish_mode=Project.PUBLISH_MODE_EDIT, project__owner=self.global_user).first(),
                'updated_data': {
                    'applicationBlob': {'video': {'vendor': 'youtube', 'id': 'not valid ID!'}},
                },
                'expected_result': 400,
            },
            {
                'get_object': lambda: Lesson.objects.filter(application=self.VIDEO_APP, project__publish_mode=Project.PUBLISH_MODE_EDIT, project__owner=self.global_user).first(),
                'updated_data': {
                    'applicationBlob': {'video': {'vendor': 'youtube', 'id': '1234567890a', 'meta': {'duration': 'PT15M33'}}},
                },
                'expected_result': 400,
            },
        ]
        self.invalid_objects_patch = {
            'user': get_user_model().objects.get(id=2),
            'get_object': lambda: Lesson.objects.filter(project__owner_id=2, project__publish_mode=Project.PUBLISH_MODE_EDIT)[0],
            'invalid_patches': [{
                'data': {'title': '*Too Long Title*'*12},
            },]
        }
        self.field_to_patch = {
            'field': 'title',
            'value': '*NEW TITLE*',
            'exclude': 'applicationBlob',
        }
        self.bulk_actions = ['post', 'put', 'patch', 'delete',]
        self.api_list_url = reverse('api:project-lesson-list', kwargs={'project_pk': self.project.id})
        self.api_details_url = 'api:project-lesson-detail'
        self.non_existant_obj_details_url = reverse('api:project-lesson-detail', kwargs={'project_pk': self.project.id, 'pk': 4444})
        self.all_user_objects = self.project.lessons.filter(
            Q(project__publish_mode=Project.PUBLISH_MODE_PUBLISHED)
        ).order_by('id')
        self.allow_unauthenticated_get = False  #unpublished project lessons are not accessible
        self.api_list_url_published = reverse('api:project-lesson-list', kwargs={'project_pk': self.project_published.id})
        self.all_public_objects_published = self.project_published.lessons.all()
        self.serializer = LessonSerializer
        self.sort_key = 'id'
        self.free_text_fields = ['title',]
        self.object_to_post = {
            'title': 'Testing 101',
            'duration': 45,
            'application': settings.LESSON_APPS['Video']['db_name'],
            'applicationBlob': {
                'video': {
                    'vendor': 'youtube',
                    'id': '1234567890a',
                },
            },
            'projectId': self.project.id,
            'order': 0,
        }
        self.object_to_delete = self.project.lessons.filter(project__owner=self.global_user[0])[0]


    def get_api_details_url(self, obj):
        return reverse('api:project-lesson-detail', kwargs={'project_pk': obj.project.id, 'pk': obj.pk})

    def setUp(self):

        super(LessonsInProjectsTests, self).setUp()

        self.all_user_objects = Project.objects.get(
            id=self.project.id
        ).lessons.all()

        self.all_public_objects = self.all_user_objects


    def test_get_list_published_everyone_can(self):
        '''Tests that everyone can get a list of lessons of a published project'''
        self.client.force_authenticate(None)
        self.test_get_list(self.api_list_url_published, self.all_public_objects_published)

    def test_get_object_published_everyone_can(self, objs_from_db=None):
        '''Tests that everyone can get a lesson of a published project'''
        self.client.force_authenticate(None)
        self.test_get_object(self.all_public_objects_published)


    def helper_assert_ordered(self, parent_project_obj):
        '''Helper method to assert that max order is always count-1'''
        count = parent_project_obj.lessons.count()
        if count:
            self.assertEqual(
                parent_project_obj.lessons.aggregate(max_order=Max('order'))['max_order'],
                count - 1
            )


    def test_can_get_lesson_in_project(self):
        """User can get lesson that is in the requested project"""
        lesson_in_project = self.all_user_objects[0] if len(self.all_user_objects) else None
        resp = self.client.get(self.get_api_details_url(lesson_in_project))
        self.assertEqual(resp.status_code, 200)

    def test_can_not_get_lesson_not_in_project(self):
        """User can not get a lesson that is not in the requested project"""
        lesson_not_in_project = Lesson.objects.exclude(id__in=[l.id for l in self.all_user_objects]).all()[0]
        resp = self.client.get(reverse(self.api_details_url, kwargs={'project_pk': self.project.id, 'pk': lesson_not_in_project.id}))
        self.assertEqual(resp.status_code, 404)

    def test_post_new_lesson_with_order_to_project_over_end(self):
        """Post a new lesson to a project in the right order position over the end (order greater than count)"""
        parent_project_obj = Project.objects.filter(publish_mode=Project.PUBLISH_MODE_EDIT, owner=self.global_user).annotate(num_lessons=Count('lessons')).order_by('-num_lessons')[0]
        self.assertGreaterEqual(parent_project_obj.num_lessons, 1, msg='Make sure to pick a project that contains lessons')
        api_list_url = reverse('api:project-lesson-list', kwargs={'project_pk': parent_project_obj.id})

        # add lesson to the end:
        lesson_to_post = copy.deepcopy(self.object_to_post)
        lessons_count = parent_project_obj.lessons.count()
        lesson_order = lessons_count + 10
        lesson_to_post['order'] = lesson_order
        resp = self.client.post(
            api_list_url,
            lesson_to_post,
            'json'
        )
        self.assertIn(resp.status_code, [200, 201, 202, 203])
        resp_lesson = self.client.get(reverse('api:project-lesson-detail', kwargs={'project_pk': parent_project_obj.id, 'pk': resp.data['id']}))
        self.assertEqual(resp_lesson.status_code, 200)
        self.assertEqual(resp_lesson.data['order'], lessons_count)
        self.helper_assert_ordered(parent_project_obj)

    def test_post_new_lesson_with_order_to_project_in_middle(self):
        """Post a new lesson to a project in the right order position in the middle"""
        parent_project_obj = Project.objects.filter(publish_mode=Project.PUBLISH_MODE_EDIT, owner=self.global_user).annotate(num_lessons=Count('lessons')).order_by('-num_lessons')[0]
        self.assertGreaterEqual(parent_project_obj.num_lessons, 1, msg='Make sure to pick a project that contains lessons')
        api_list_url = reverse('api:project-lesson-list', kwargs={'project_pk': parent_project_obj.id})

        # add lesson in the middle:
        lesson_to_post = copy.deepcopy(self.object_to_post)
        lesson_order = int(parent_project_obj.lessons.count()/2)
        lesson_to_post['order'] = lesson_order
        resp = self.client.post(
            api_list_url,
            lesson_to_post,
            'json'
        )
        self.assertIn(resp.status_code, [200, 201, 202, 203])
        resp_lesson = self.client.get(reverse('api:project-lesson-detail', kwargs={'project_pk': parent_project_obj.id, 'pk': resp.data['id']}))
        self.assertEqual(resp_lesson.status_code, 200)
        self.assertEqual(resp_lesson.data['order'], lesson_order)
        self.helper_assert_ordered(parent_project_obj)

    def test_disallow_post_new_lesson_to_published_project(self):
        """Post a new lesson to a project in the right order position"""
        parent_project_obj = Project.objects.filter(publish_mode=Project.PUBLISH_MODE_PUBLISHED, owner=self.global_user)[0]
        api_list_url = reverse('api:project-lesson-list', kwargs={'project_pk': parent_project_obj.id})

        # add lesson to the end:
        lesson_to_post = copy.deepcopy(self.object_to_post)
        resp = self.client.post(
            api_list_url,
            lesson_to_post,
            'json'
        )
        self.assertIn(resp.status_code, [400, 403])

    def test_post_new_lesson_without_order_to_project_is_appended_last(self):
        """Post a new lesson to a project in the right order position"""
        parent_project_obj = Project.objects.filter(publish_mode=Project.PUBLISH_MODE_EDIT, owner=self.global_user).annotate(num_lessons=Count('lessons')).order_by('-num_lessons')[0]
        api_list_url = reverse('api:project-lesson-list', kwargs={'project_pk': parent_project_obj.id})

        # add lesson to the end:
        lesson_to_post = copy.deepcopy(self.object_to_post)
        del lesson_to_post['order']
        resp = self.client.post(
            api_list_url,
            lesson_to_post,
            'json'
        )
        self.assertEqual(resp.status_code, 201)

        num_lessons = parent_project_obj.lessons.count()
        self.assertEqual(resp.data['order'], num_lessons-1)

    def test_update_order_of_lesson_only_in_published_project(self):
        """Post a new lesson to a project in the right order position"""
        # Published project - disallow:
        parent_project_obj = Project.objects.filter(publish_mode=Project.PUBLISH_MODE_PUBLISHED, owner=self.global_user).annotate(num_lessons=Count('lessons')).order_by('-num_lessons')[0]
        self.assertGreaterEqual(parent_project_obj.num_lessons, 2, msg='Make sure to pick a project that contains at least 2 lessons')
        lesson = Lesson.objects.filter(project=parent_project_obj, project__owner=self.global_user).order_by('order')[parent_project_obj.lessons.count()-2]
        api_obj = self.client.get(reverse('api:project-lesson-detail', kwargs={'project_pk': parent_project_obj.id, 'pk': lesson.id}))
        self.assertGreaterEqual(api_obj.data['order'], 1)
        api_obj_order_patch = {
            'order': max(0, api_obj.data['order']-2),
        }
        resp = self.client.patch(
            reverse('api:project-lesson-detail', kwargs={'project_pk': parent_project_obj.id, 'pk': lesson.id}),
            api_obj_order_patch,
            'json'
        )
        self.assertEqual(resp.status_code, 403)
        resp_lesson = self.client.get(reverse('api:project-lesson-detail', kwargs={'project_pk': parent_project_obj.id, 'pk': lesson.id}))
        self.assertEqual(resp_lesson.data['order'], lesson.order)
        self.helper_assert_ordered(parent_project_obj)

        # Unpublished project - allow:
        parent_project_obj = Project.objects.filter(publish_mode=Project.PUBLISH_MODE_EDIT, owner=self.global_user).annotate(num_lessons=Count('lessons')).order_by('-num_lessons')[0]
        self.assertGreaterEqual(parent_project_obj.num_lessons, 2, msg='Make sure to pick a project that contains at least 2 lessons')
        lesson = Lesson.objects.filter(project=parent_project_obj, project__owner=self.global_user).order_by('order')[parent_project_obj.lessons.count()-2]
        api_obj = self.client.get(reverse('api:project-lesson-detail', kwargs={'project_pk': parent_project_obj.id, 'pk': lesson.id}))
        self.assertGreaterEqual(api_obj.data['order'], 1)
        api_obj_order_patch = {
            'order': max(0, api_obj.data['order']-2),
        }
        resp = self.client.patch(
            reverse('api:project-lesson-detail', kwargs={'project_pk': parent_project_obj.id, 'pk': lesson.id}),
            api_obj_order_patch,
            'json'
        )
        self.assertEqual(resp.status_code, 200)
        resp_lesson = self.client.get(reverse('api:project-lesson-detail', kwargs={'project_pk': parent_project_obj.id, 'pk': lesson.id}))
        self.assertEqual(resp_lesson.data['order'], api_obj_order_patch['order'])
        self.helper_assert_ordered(parent_project_obj)

    def test_delete_lesson_only_from_unpublished_project(self):
        """Allow delete lesson only from unpublished project"""
        # Published project - disallow delete:
        parent_project_obj = Project.objects.filter(publish_mode=Project.PUBLISH_MODE_PUBLISHED, owner=self.global_user).annotate(num_lessons=Count('lessons')).order_by('-num_lessons')[0]
        self.assertGreaterEqual(parent_project_obj.num_lessons, 1, msg='Make sure to pick a project that contains lessons')
        lesson = parent_project_obj.lessons.filter(project__owner=self.global_user)[0]
        resp = self.client.delete(reverse('api:project-lesson-detail', kwargs={'project_pk': parent_project_obj.id, 'pk': lesson.id}))
        self.assertIn(resp.status_code, [400, 403])
        self.assertIn(lesson.id, [x.id for x in parent_project_obj.lessons.all()])

        # Unpublished project - allow delete:
        parent_project_obj = Project.objects.filter(publish_mode=Project.PUBLISH_MODE_EDIT, owner=self.global_user).annotate(num_lessons=Count('lessons')).order_by('-num_lessons')[0]
        self.assertGreaterEqual(parent_project_obj.num_lessons, 1, msg='Make sure to pick a project that contains lessons')
        lesson = parent_project_obj.lessons.filter(project__owner=self.global_user)[0]
        resp = self.client.delete(reverse('api:project-lesson-detail', kwargs={'project_pk': parent_project_obj.id, 'pk': lesson.id}))
        self.assertEqual(resp.status_code, 204)
        self.assertNotIn(lesson.id, [x.id for x in parent_project_obj.lessons.all()])
        self.helper_assert_ordered(parent_project_obj)

        # check that parent 'updated' was changed:
        old_parent_updated = parent_project_obj.updated
        parent_project_obj = Project.objects.get(id=parent_project_obj.id)
        self.assertGreater(parent_project_obj.updated, old_parent_updated)

    @unittest.skip('Multi-Threading Not Implemented')
    def test_multiple_post_new_lessons_to_single_project(self):
        '''
        Multiple POSTs of new lessons to a single project at once (multi-threaded).
        This is to check transaction and locking for order field.
        '''
        parent_project_obj = Project.objects.filter(publish_mode=Project.PUBLISH_MODE_EDIT, owner=self.global_user).annotate(num_lessons=Count('lessons')).order_by('-num_lessons')[0]
        self.assertGreaterEqual(parent_project_obj.num_lessons, 1, msg='Make sure to pick a project that contains lessons')
        api_list_url = reverse('api:project-lesson-list', kwargs={'project_pk': parent_project_obj.id})
        lesson_order = int(parent_project_obj.lessons.count()/2)

        threads_responses = []
        def helper_post_lesson(cli, l_obj):
            resp = cli.post(
                api_list_url,
                l_obj,
                'json'
            )
            threads_responses.append(resp)

        threads_requests = []
        try:
            for i in xrange(5):
                lesson_to_post = copy.deepcopy(self.object_to_post)
                lesson_to_post['order'] = lesson_order
                th = threading.Thread(
                    target=helper_post_lesson,
                    args=(self.client, lesson_to_post),
                )
                th.daemon = False
                threads_requests.append(th)
                th.start()
        except Exception as exc:
            raise exc
        finally:
            #join all requests threads
            for th in threads_requests:
                th.join()
        self.helper_assert_ordered(parent_project_obj)


    @unittest.skip('Not implemented')
    def test_invlaid_data_in_post(self):
        pass

    def test_patch_application_blob_as_dict(self):
        lesson = self.all_user_objects.exclude(application=self.VIDEO_APP).filter(application_blob__regex=r'.{10}.*')[0]
        api_lesson = self.client.get(self.get_api_details_url(lesson)).data
        self.assertGreaterEqual(len(str(api_lesson['applicationBlob'])), 10)
        api_lesson['applicationBlob']['this is only for the test'] = 5555
        resp = self.client.patch(api_lesson['self'], json.dumps({
            'applicationBlob': api_lesson['applicationBlob'],
            'id': api_lesson['id'],
        }, cls=DjangoJSONEncoder), content_type='application/json')
        self.assertIn(resp.status_code, range(200,205))
        # Check that application blob in response contains new key
        self.assertEqual(resp.data['applicationBlob'], api_lesson['applicationBlob'])
        # Check that application blob in DB contains new key
        self.assertEqual(resp.data['applicationBlob'], Lesson.objects.get(id=lesson.id).application_blob)

    def test_patch_application_blob_as_string(self):
        lesson = self.all_user_objects.exclude(application=self.VIDEO_APP).filter(application_blob__regex=r'.{10}.*')[0]
        api_lesson = self.client.get(self.get_api_details_url(lesson)).data
        self.assertGreaterEqual(len(str(api_lesson['applicationBlob'])), 10)
        api_lesson['applicationBlob']['this is only for the test'] = 5555
        api_lesson['applicationBlob']['text with unicode character'] = u'\u2126 is electricity symbol'
        api_lesson['applicationBlob']['boolean value'] = True  # will be 'true' in the json string
        application_blob_json_str = json.dumps(api_lesson['applicationBlob'])
        resp = self.client.patch(api_lesson['self'], json.dumps({
            'applicationBlob': application_blob_json_str,
            'id': api_lesson['id'],
        }, cls=DjangoJSONEncoder), content_type='application/json')
        self.assertIn(resp.status_code, range(200,205))
        # Check that application blob in response contains new key
        self.assertEqual(resp.data['applicationBlob'], api_lesson['applicationBlob'])
        # Check that application blob in DB contains new key
        self.assertEqual(resp.data['applicationBlob'], Lesson.objects.get(id=lesson.id).application_blob)

    def test_validate_application_blob_for_video(self):
        parent_project_obj = Project.objects.filter(publish_mode=Project.PUBLISH_MODE_EDIT, owner=self.global_user)[0]
        api_list_url = reverse('api:project-lesson-list', kwargs={'project_pk': parent_project_obj.id})

        # Add lesson without required application blob for video:
        lesson_to_post = copy.deepcopy(self.object_to_post)
        lesson_to_post['application'] = settings.LESSON_APPS['Video']['db_name']
        lesson_to_post['applicationBlob']['video2'] = lesson_to_post['applicationBlob'].pop('video')
        resp = self.client.post(
            api_list_url,
            lesson_to_post,
            'json'
        )
        self.assertIn(resp.status_code, xrange(200, 202))

        # Publish parent project:
        resp2 = self.client.patch(
            reverse('api:project-detail', kwargs={'pk': parent_project_obj.pk}),
            json.dumps({
                'publishMode': Project.PUBLISH_MODE_REVIEW,
            }),
            content_type='application/json',
        )
        self.assertEqual(resp2.status_code, 400)
        self.assertIn('publishErrors', resp2.data)
        self.assertIn('applicationBlob', resp2.data['publishErrors']['lessons'][resp.data['id']])

    def test_validate_application_blob_for_circuits(self):
        parent_project_obj = Project.objects.filter(publish_mode=Project.PUBLISH_MODE_EDIT, owner=self.global_user)[0]
        api_list_url = reverse('api:project-lesson-list', kwargs={'project_pk': parent_project_obj.id})

        # Add lesson without required application blob for circuits:
        lesson_to_post = copy.deepcopy(self.object_to_post)
        lesson_to_post['application'] = settings.LESSON_APPS['Circuits']['db_name']
        lesson_to_post['applicationBlob']['startCircuitId2'] = 167684
        resp = self.client.post(
            api_list_url,
            lesson_to_post,
            'json'
        )
        self.assertIn(resp.status_code, xrange(200, 202))

        # Publish parent project:
        resp2 = self.client.patch(
            reverse('api:project-detail', kwargs={'pk': parent_project_obj.pk}),
            json.dumps({
                'publishMode': Project.PUBLISH_MODE_REVIEW,
            }),
            content_type='application/json',
        )
        self.assertEqual(resp2.status_code, 400)
        self.assertIn('publishErrors', resp2.data)
        self.assertIn('applicationBlob', resp2.data['publishErrors']['lessons'][resp.data['id']])

    def test_validate_application_blob_for_instructables(self):
        parent_project_obj = Project.objects.filter(publish_mode=Project.PUBLISH_MODE_EDIT, owner=self.global_user)[0]
        api_list_url = reverse('api:project-lesson-list', kwargs={'project_pk': parent_project_obj.id})

        # Add lesson without required application blob for instructables:
        lesson_to_post = copy.deepcopy(self.object_to_post)
        lesson_to_post['application'] = settings.LESSON_APPS['Instructables']['db_name']
        lesson_to_post['applicationBlob']['instructables2'] = { 'urlId': 'instruct-lesson-01' }
        resp = self.client.post(
            api_list_url,
            lesson_to_post,
            'json'
        )
        self.assertIn(resp.status_code, xrange(200, 202))

        # Try add invalid applicationBlob:
        resp1 = self.client.patch(
            resp.data['self'],
            json.dumps({
                'applicationBlob': {
                    'instructables': {
                        'urlId': 'invalid/slug',
                    }
                }
            }),
            content_type='application/json',
        )
        self.assertEqual(resp1.status_code, 400)
        self.assertIn('applicationBlob', resp1.data)

        # Publish parent project:
        resp2 = self.client.patch(
            reverse('api:project-detail', kwargs={'pk': parent_project_obj.pk}),
            json.dumps({
                'publishMode': Project.PUBLISH_MODE_REVIEW,
            }),
            content_type='application/json',
        )
        self.assertEqual(resp2.status_code, 400)
        self.assertIn('publishErrors', resp2.data)
        self.assertIn('applicationBlob', resp2.data['publishErrors']['lessons'][resp.data['id']])

    def test_put_lesson_embed_steps_omitted(self):
        '''
        Checks that PUT to lesson embedded steps without 'steps' attribute does not affect the steps of the lesson.
        '''
        # Get a lesson with at least 3 steps.
        lesson = self.all_user_objects.annotate(
            steps_num=Count('steps')
        ).filter(steps_num__gte=3)[0]
        lesson_steps_ids = list(lesson.steps.values_list('id', flat=True))

        api_lesson = self.client.get(
            self.get_api_details_url(lesson),
            {'embed': 'steps'}
        ).data
        del api_lesson['steps']

        resp = self.client.put(
            self.get_api_details_url(lesson) + '?embed=steps',
            json.dumps(api_lesson, cls=DjangoJSONEncoder),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertListEqual([x['id'] for x in resp.data['steps']], lesson_steps_ids)

    def test_fail_to_delete_published_lesson(self):
        # create lesson and maintain its primary key
        lesson = Lesson.objects.create(title='Lesson to be deleted', project=self.project)
        pk = lesson.pk
        # delete lesson
        response = self.client.delete(self.get_api_details_url(lesson))
        # validate deletion
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        # make sure lesson does not exist in DB
        with self.assertRaises(Lesson.DoesNotExist):
            deleted_lesson = Lesson.objects.get(pk=pk)

        #delete a lesson of a published project - disallowed:
        lesson = Lesson.objects.filter(project__owner=self.global_user, project__publish_mode=Project.PUBLISH_MODE_PUBLISHED).first()
        pk = lesson.pk
        # delete lesson
        response = self.client.delete(self.get_api_details_url(lesson))
        # verify deletion was not allowed
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        # verify lesson still in DB
        Lesson.objects.get(pk=pk)

    def test_app_user_can_edit_app_lessons_by_other_users(self):
        groups = Group.objects.filter(name__in=[a for a,_ in Lesson.APPLICATIONS])
        self.assertGreaterEqual(len(groups), 1)  #check that there are groups in the database

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
            #   3. belongs to this application.
            app_lesson = Lesson.objects.filter(
                project__publish_mode=Project.PUBLISH_MODE_EDIT,
                application=group.name
            ).first()
            app_project = app_lesson.project
            self.assertEqual(app_project.publish_mode, Project.PUBLISH_MODE_EDIT)

            # Check that the lesson is editable by the user.
            resp = self.client.patch(
                self.get_api_details_url(app_lesson),
                json.dumps({'title': app_lesson.title + '.'}, cls=DjangoJSONEncoder),
                content_type='application/json',
            )
            self.assertEqual(resp.status_code, status.HTTP_200_OK)
            app_lesson_test = Lesson.objects.get(id=app_lesson.id)
            self.assertEqual(app_lesson_test.title, app_lesson.title + '.')

            # Restore database
            app_lesson.save()
            user.delete()

    def test_app_user_cant_edit_other_apps_lessons(self):
        groups = Group.objects.filter(name__in=[a for a,_ in Lesson.APPLICATIONS])
        self.assertGreaterEqual(len(groups), 1)  #check that there are groups in the database

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
            #   3. belongs to this application.
            app_lesson = Lesson.objects.filter(
                project__publish_mode=Project.PUBLISH_MODE_EDIT
            ).exclude(
                application=group.name
            ).first()
            app_project = app_lesson.project
            self.assertEqual(app_project.publish_mode, Project.PUBLISH_MODE_EDIT)

            # Check that the lesson is editable by the user.
            resp = self.client.patch(
                self.get_api_details_url(app_lesson),
                json.dumps({}, cls=DjangoJSONEncoder),
                content_type='application/json',
            )
            self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

            # Restore database
            user.delete()

    def test_lesson_editable_by_project_owner(self):
        '''
        Tests that a lesson is always editable by the project owner, even in case the lesson is owned by another user.
        '''
        #get lesson of unpublished project:
        lesson = Lesson.objects.filter(project__publish_mode=Project.PUBLISH_MODE_EDIT, project__owner=self.global_user).first()
        lesson_details_api = self.get_api_details_url(lesson)

        #lesson project owner - allowed get and edit:
        self.client.force_authenticate(self.global_user)

        resp = self.client.get(lesson_details_api)
        self.assertEqual(resp.status_code, 200)
        resp2 = self.client.put(
            lesson_details_api,
            data=json.dumps(resp.data, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp2.status_code, 200)

        # check that parent 'updated' was changed:
        last_updated_obj = Lesson.objects.get(id=resp2.data['id'])
        self.assertEqual(last_updated_obj.project.updated, last_updated_obj.updated)

        #another user - get not found:
        user = get_user_model().objects.exclude(
            Q(pk=lesson.project.owner.pk) |
            Q(pk__in=lesson.project.owner.guardians.all()) |
            Q(pk__in=lesson.project.owner.delegates.all())
        ).first()
        self.client.force_authenticate(user)

        resp = self.client.get(lesson_details_api)
        self.assertEqual(resp.status_code, 404)
        resp2 = self.client.put(
            lesson_details_api,
            data=json.dumps(resp.data, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp2.status_code, 404)

    def test_post_multiple_lessons_to_project_using_single_request(self):
        #get lessons list:
        response = self.client.get(self.api_list_url)
        self.assertEqual(response.status_code, 200)
        num_existing_lessons = response.data['count']

        # create a list of lessons to post in bulk
        num_lessons=12
        lessons = []
        for i in xrange(0,num_lessons):
            lesson = copy.deepcopy(self.object_to_post)
            lesson['order'] = i
            lessons.append(lesson)
        # post lessons in bulk using a single post request
        response = self.client.post(
            self.api_list_url,
            json.dumps(lessons, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertIn(response.status_code, xrange(200, 205))
        # make sure the returned object contains the list of lessons (note bulk update does not have pagination)
        self.assertEqual(len(response.data), num_lessons)

        # check that parent 'updated' was changed:
        last_updated_obj = Lesson.objects.get(id=response.data[-1]['id'])
        self.assertEqual(last_updated_obj.project.updated, last_updated_obj.updated)

        # get project and verify data
        response = self.client.get(self.api_list_url)
        self.assertEqual(response.status_code,200)
        # verify again number of lessons in project
        self.assertEqual(response.data['count'], num_existing_lessons+num_lessons)

    def test_update_multiple_lessons_to_project_using_single_request(self):
        # get lesson details of this project
        response = self.client.get(self.api_list_url)
        # get lessons from response and update about half of them
        lessons = response.data['results']
        num_lessons = len(lessons)
        num_lessons_total = response.data['count']
        num_lessons_updated = int(num_lessons/2)+1
        updated_lessons_ids = []
        for lesson in lessons[:num_lessons_updated]:
            lesson['title']+=' updated'
            updated_lessons_ids.append(lesson['id'])

        # update lesson details of this project
        response = self.client.put(
            self.api_list_url,
            json.dumps(lessons, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertIn(response.status_code, xrange(200, 205))

        # check that parent 'updated' was changed:
        last_updated_obj = Lesson.objects.get(id=response.data[-1]['id'])
        self.assertEqual(last_updated_obj.project.updated, last_updated_obj.updated)

        # get updated lessons from server
        response = self.client.get(self.api_list_url)
        self.assertIn(response.status_code, xrange(200, 205))

        self.assertEqual(response.data['count'], num_lessons_total)
        for lesson in [l for l in response.data['results'] if l['id'] in updated_lessons_ids]:
            # verify there was an update
            self.assertTrue(lesson['title'].endswith('updated'))

        # update again, but screw up a single lesson, get list of errors
        lessons[int(num_lessons/2)].pop('title')
        # update lesson details of this project
        response = self.client.put(
            self.api_list_url,
            json.dumps(lessons, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(response.status_code,400)
        # we should get a list of errors, equal to the number of lessons
        self.assertEqual(len(response.data), num_lessons)
        # verify we have an error object in the faulty lesson (non empty dictionaries evaluate to True)
        self.assertTrue(bool(response.data[num_lessons/2]))
        # verify all other objects do not have errors
        response.data.pop(int(num_lessons/2))
        self.assertTrue(all([bool(response.data)]))

    def test_delete_lesson_from_project_removes_from_extra_lessons_groups(self):
        """Checks that when deleting a lesson from project, the lesson id is removed from any lessons group in its project.extra lessonsInit groups."""
        #get unpublished project with some lessons and pick a lesson:
        lesson_application = settings.LESSON_APPS['Tinkercad']['db_name']
        parent_project_obj = Project.objects.filter(
            lessons__application=lesson_application,
        ).annotate(
            num_lessons=Count('lessons')
        ).filter(
            publish_mode=Project.PUBLISH_MODE_EDIT,
            owner=self.global_user,
            num_lessons__gte=2,
        ).order_by('-num_lessons')[0]
        self.assertGreaterEqual(parent_project_obj.num_lessons, 2, msg='Make sure to pick a project that contains at least 2 lessons of %s' % lesson_application)
        lesson, lesson2 = parent_project_obj.lessons.filter(application=lesson_application)[:2]

        # Lesson is single in a group - group should not exist when deleted.

        #add the lesson its project.extra lessonsInit groups:
        resp = self.client.patch(
            reverse('api:project-detail', kwargs={'pk': parent_project_obj.pk}),
            json.dumps({
                'extra': {
                    'lessonsInit': [{
                        'lessonsIds': [lesson.id],
                        'initCanvasId': 'A1B2C3',
                    },]
                }
            }, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['extra']['lessonsInit'][0]['lessonsIds'], [lesson.id])
        #delete the lesson:
        resp = self.client.delete(reverse('api:project-lesson-detail', kwargs={'project_pk': parent_project_obj.id, 'pk': lesson.id}))
        self.assertEqual(resp.status_code, 204)
        #get the project and check that the lesson deleted is not in lessonsInit groups:
        resp = self.client.get(reverse('api:project-detail', kwargs={'pk': parent_project_obj.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data['extra'])

        #restore - save lesson into project again:
        lesson.save()

        # Lesson is not single in a group - group should exist but lesson should not exist when lesson is deleted.

        #add the lesson its project.extra lessonsInit groups:
        resp = self.client.patch(
            reverse('api:project-detail', kwargs={'pk': parent_project_obj.pk}),
            json.dumps({
                'extra': {
                    'lessonsInit': [{
                        'lessonsIds': [lesson.id, lesson2.id],
                        'initCanvasId': 'A1B2C3',
                    },]
                }
            }, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['extra']['lessonsInit'][0]['lessonsIds'], [lesson.id, lesson2.id])
        #delete the lesson:
        resp = self.client.delete(reverse('api:project-lesson-detail', kwargs={'project_pk': parent_project_obj.id, 'pk': lesson.id}))
        self.assertEqual(resp.status_code, 204)
        #get the project and check that the lesson deleted is not in lessonsInit groups:
        resp = self.client.get(reverse('api:project-detail', kwargs={'pk': parent_project_obj.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(resp.data['extra'])
        self.assertEqual(len(resp.data['extra']['lessonsInit']), 1)
        self.assertEqual(resp.data['extra']['lessonsInit'][0]['lessonsIds'], [lesson2.id])
        self.assertEqual(resp.data['extra']['lessonsInit'][0]['initCanvasId'], 'A1B2C3')

        #restore - save lesson into project again:
        lesson.save()

        # Lesson is 1 of 2 lessons in a group with no initCanvasId - group should not exist when lesson is deleted.

        #add the lesson its project.extra lessonsInit groups:
        resp = self.client.patch(
            reverse('api:project-detail', kwargs={'pk': parent_project_obj.pk}),
            json.dumps({
                'extra': {
                    'lessonsInit': [{
                        'lessonsIds': [lesson.id, lesson2.id],
                        'custom_key': 'This key will not keep the group alive...',
                    },]
                }
            }, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['extra']['lessonsInit'][0]['lessonsIds'], [lesson.id, lesson2.id])
        #delete the lesson:
        resp = self.client.delete(reverse('api:project-lesson-detail', kwargs={'project_pk': parent_project_obj.id, 'pk': lesson.id}))
        self.assertEqual(resp.status_code, 204)
        #get the project and check that the lesson deleted is not in lessonsInit groups:
        resp = self.client.get(reverse('api:project-detail', kwargs={'pk': parent_project_obj.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data['extra'])

        #restore - save lesson into project again:
        lesson.save()


    def test_lessons_list_non_searchable(self):
        project = self.project_published
        project_all_lessons = project.lessons.all()
        self.assertTrue(project.is_searchable, msg='Assumed starting project that is searchable.')

        user = get_user_model().objects.exclude(pk=project.owner.pk).exclude(pk__in=project.registrations.all())[0]
        self.client.force_authenticate(user)

        num_project_all_lessons = project_all_lessons.count()

        project_lessons_list_url = reverse('api:project-lesson-list', kwargs={'project_pk': project.pk})

        resp = self.client.get(project_lessons_list_url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], num_project_all_lessons)

        # Hide project
        project.is_searchable = False
        project.save()

        # GET /projects/:id/lessons/
        resp = self.client.get(project_lessons_list_url, {'pageSize': num_project_all_lessons})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], num_project_all_lessons)
        self.assertSetEqual(
            set([x['id'] for x in resp.data['results']]),
            set([x.id for x in project_all_lessons])
        )
