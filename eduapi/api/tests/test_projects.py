import json
import copy
import unittest

from django.conf import settings
from django.db.models import Q, Count
from django.contrib.auth.models import Group
from django.core.urlresolvers import reverse
from django.contrib.auth import get_user_model
from django.core.serializers.json import DjangoJSONEncoder
from django.core import management

from rest_framework.test import APITestCase as DRFTestCase
from rest_framework import status

from common_project_classroom_tests import ClassroomProjectTestsBase
from api_test_case.decorators import should_check_action
from edu_api_test_case import EduApiTestCase

from ..serializers import ProjectSerializer
from ..models import (
    Project,
    Lesson,
    ProjectState,
    OwnerDelegate,
)

from marketplace.models import Purchase

class ProjectTests(EduApiTestCase, DRFTestCase):
    '''
    Tests the Project API.
    '''

    fixtures = ['test_projects_fixture_1.json']
    model = Project

    # Specific configuration for common_project_classroom_tests
    embedded_model = Lesson
    embedded_obj_s = 'lesson'
    embedded_obj_p = 'lessons'
    embedded_list_ids = 'lessonsIds'
    embedded_through_model = None

    def api_test_init(self):
        super(ProjectTests, self).api_test_init()

        self.put_actions = [
            # Successful PUT
            {
                'get_object': lambda: Project.objects.exclude(title='1111111').filter(publish_mode=Project.PUBLISH_MODE_EDIT,owner=self.global_user).first(),
                'updated_data': {'title': '1111111'},
            },
            # Can't edit published lesson
            # {
            #     'get_object': lambda: Project.objects.filter(publish_mode=Project.PUBLISH_MODE_PUBLISHED,owner=self.global_user).first(),
            #     'updated_data': {'title': '1111111'},
            #     'expected_result': 400,
            # },
            # Empty title
            {
                'get_object': lambda: Project.objects.filter(publish_mode=Project.PUBLISH_MODE_EDIT,owner=self.global_user).first(),
                'updated_data': {'title': ''},
                'expected_result': 400,
                'expected_response': {"title": ["This field may not be blank."]},
            },
            # Can't edit project by other user.
            {
                'user': get_user_model().objects.get(id=4),
                'expected_result': 403,
                'get_object': lambda: Project.objects.filter(publish_mode=Project.PUBLISH_MODE_PUBLISHED).exclude(owner_id=4)[0],
            },
            # Can't edit project if not logged in.
            {
                'user': None,
                'expected_result': 401,
                'get_object': lambda: Project.objects.filter(publish_mode=Project.PUBLISH_MODE_PUBLISHED)[0],
            },
        ]

        self.invalid_objects_patch = {
            'user': get_user_model().objects.get(id=2),
            'get_object': lambda: Project.objects.filter(owner_id=2, publish_mode=Project.PUBLISH_MODE_EDIT)[0],
            'invalid_patches': [
                {'data': {'bannerImage': 'http://test.com/invalid/'+'abcdefghij'*52+'.jpg'}},
                {'data': {'cardImage': 'http://test.com/invalid/'+'abcdefghij'*52+'.jpg'}},
                {'data': {'teacherInfo':{'teachersFiles': [{
                                                            'url': 'http://test.com/file.zip',
                                                            'name': 'Project Resources',
                                                            'time': '2015-01-04T08:06:16.606Z',
                                                            #missing 'size' field
                    }]}
                }},
                {'data': {'teacherInfo':{'teachersFiles': [{
                        'url': 'http://test.com/file.zip',
                        'name': 'Project Resources',
                        'size': 89125,
                        'time': '2015-01-04T08:06:16.606Z',
                        'additional_field': 'Not allowed!',
                    }]}
                }},
                {'data': {'teacherInfo':{'teachersFiles': [{
                        'url': 'test.com/invalid_url/file.zip',
                        'name': 'Project Resources',
                        'size': 89125,
                        'time': '2015-01-04T08:06:16.606Z',
                    }]}
                }},
                {'data': {'teacherInfo':{'teachersFiles': [{
                        'url': 'http://test.com/file.zip',
                        'name': 'Project Resources',
                        'size': 89125,
                        'time': 'Thursday, 3rd Jan 2015',  #invalid time
                    }]}
                }},
                {'data': {'teacherInfo':{'teachersFiles': [{
                        'url': 'http://test.com/file.zip',
                        'name': '*Too Long Name*'*30,
                        'size': 89125,
                        'time': '2015-01-04T08:06:16.606Z',
                    }]}
                }}],
        }
        self.global_user = get_user_model().objects.filter(id=2)
        self.api_list_url = reverse('api:project-list')
        self.api_details_url = 'api:project-detail'
        self.non_existant_obj_details_url = reverse('api:project-detail', kwargs={'pk': 4444})
        self.all_user_objects = Project.objects.filter(
            Q(publish_mode=Project.PUBLISH_MODE_PUBLISHED, is_searchable=True)
            | Q(owner=self.global_user[0]) | Q(owner__in=self.global_user[0].delegators.all()) | Q(owner__in=self.global_user[0].children.all())
            #IMPORTANT NOTE:
            #   When enable in FilterAllowedMixin to include projects published and purchased
            #   (even not searchable) then uncomment the rest of the following line of code:
            # | Q(publish_mode=Project.PUBLISH_MODE_PUBLISHED, pk__in=self.global_user[0].purchases.values('project'))
        ).order_by('id')
        self.all_user_objects_for_edit = Project.objects.filter(
            Q(publish_mode=Project.PUBLISH_MODE_EDIT),
            Q(owner=self.global_user) | Q(owner__in=self.global_user[0].delegators.all()) | Q(owner__in=self.global_user[0].children.all())
        )
        self.object_to_delete = self.all_user_objects.filter(publish_mode=Project.PUBLISH_MODE_EDIT)[0]
        self.all_public_objects = Project.objects.filter(
            Q(publish_mode=Project.PUBLISH_MODE_PUBLISHED),
        ).order_by('id')
        self.serializer = ProjectSerializer
        self.sort_key = 'id'
        self.filters = [
            ({'duration__gte': 20}, None,),
            ({'difficulty': 'hard', 'duration': 24}, None,),
            ({'author__id': 4}, {'owner__id': 4},),
            ({'idList': '2,3,a,,,15'}, 'ERROR',),
            ({'idList': '2'}, {'id__in': [2]},),
            ({'idList': 'a,b'}, 'ERROR',),
            ({'idList': ''}, 'ERROR',),
            ({'numberOfLessons__gt': 1}, {'lesson_count__gt': 1}),
            ({'numberOfStudents__gte': 1}, {'students_count__gte': 1}),
            ({'minPublishDate__gt': '2014-08-15'}, {'min_publish_date__gt': '2014-08-15'}),
            ({'minPublishDate__lte': '2014-08-31 12:00:00'}, {'min_publish_date__lte': '2014-08-31T12:00:00Z'}),
            ({'minPublishDate__lte': '2014-08-31 12:00:00.555'}, {'min_publish_date__lte': '2014-08-31T12:00:00.555Z'}),
            ({'minPublishDate__gte': '2014-08-31Z-invalid'}, 'ERROR'),
            ({'publishMode': 'published'}, {'publish_mode__in': ['published']}),
            ({'publishMode': 'review,ready'}, {'publish_mode__in': ['review', 'ready']}),
            ({'publishMode': 'edit,  ,,  ,, review,,ready  ,, '}, 'ERROR'),
        ]
        self.pagination = True
        self.free_text_fields = ['title', 'description', 'teacher_additional_resources',]
        self.dropfields = ['lessonsIds', 'lessons', 'state', 'enrolled', 'draft', 'origin', 'forceEditFrom',
                           'teacherInfo', 'teacher_additional_resources', 'teachers_files_list', 'prerequisites',
                           'teacher_tips', 'ngss', 'ccss', 'subject', 'grades_range', 'technology',
                           'four_cs_creativity', 'four_cs_critical', 'four_cs_communication', 'four_cs_collaboration',
                           'skills_acquired', 'learning_objectives',]
        self.object_to_post = {
            'title': 'Testing 101',
            'publishMode': Project.PUBLISH_MODE_EDIT,
            'description': 'Learn how to test Django applications using Python\'s unittest',
            'duration': 45,
            'bannerImage': 'http://placekitten.com/2048/640/',
            'cardImage': 'http://placekitten.com/1024/768/',
            'age': Project.AGES[0][0],
            'difficulty': Project.DIFFICULTIES[0][0],
            'license': Project.LICENSES[0][0],
            'tags': '3D-Design Tools,Printing',
            'teacherInfo': {
                'ngss': [Project.NGS_STANDARDS[0][0], Project.NGS_STANDARDS[1][0]],
                'ccss': [Project.CCS_STANDARDS[0][0], Project.CCS_STANDARDS[1][0]],
                'subject': [Project.SUBJECTS[0][0], Project.SUBJECTS[1][0]],
                'technology': [Project.TECHNOLOGY[0][0], Project.TECHNOLOGY[1][0]],
                'grades': [Project.GRADES[0][0], Project.GRADES[1][0]],
                'skillsAcquired': ['3D-printing', '3D-modeling'],
                'learningObjectives': ['Mesh', 'Shaders'],
                'fourCS': {
                    'creativity': '<p>Creativity</p>',
                    'critical': '<p>Critical</p>',
                    'communication': '<p>Communication</p>',
                    'collaboration': '<p>Collaboration</p>',
                }
            },
        }
        self.project_object_to_add = self.object_to_post
        self.lesson_object_to_add = {
            'title': 'Lesson 101',
            'description': 'Lesson to add to a project.',
            'application': 'video',
            'applicationBlob': {'video': {'vendor': 'youtube', 'id': '1234567890a'}},
            'duration': 30,
            'image': 'http://placekitten.com/1024/768/',
            'age': Project.AGES[0][0],
            'difficulty': Project.DIFFICULTIES[0][0],
            'license': Project.LICENSES[0][0],
            'order': 0,
        }

        self.check_fields = self.tags_success = [
                ('tags', True, 'single', 'single'),
                ('tags', True, '    a,   b     ,   ,,, c    , ,d,e,   ', 'a,b,c,d,e'),
                ('tags', True, '   a1 - B_2,  start   3-spaces', 'a1 - B_2,start   3-spaces'),
                ('tags', False, 'a?b'),
                ('tags', False, 'a!b'),
                ('tags', False, 'a@b'),
                ('tags', False, 'a#b'),
                ('tags', False, 'a&b'),
                ('tags', False, 'a$b'),
                ('tags', False, 'a*b'),
                ('tags', False, 'a+b'),
            ]

    def setUp(self):
        super(ProjectTests, self).setUp()
        self.object_to_delete = Project.objects.filter(publish_mode=Project.PUBLISH_MODE_EDIT, owner=self.global_user)[0]


    @should_check_action(actions_tested=('delete',))
    def test_cant_delete_if_not_owner(self):
        '''
        Overridden since project can be deleted also by delegates.
        Test that a user who's not the owner (or delegate, for project) can't DELETE an object.
        '''

        if not hasattr(self.all_user_objects.first(), 'owner'):
            return

        for db_obj in self.all_user_objects:

            for user in get_user_model().objects.all():

                if user == db_obj.owner or (user in db_obj.owner.guardians.all()):
                    continue
                if user in db_obj.owner.delegates.all():
                    continue

                self.client.force_authenticate(user)

                resp = self.client.delete(
                    self.get_api_details_url(db_obj),
                )

                self.assertIn(resp.status_code, [401,404,403])


    def _get_new_project_with_lessons(self, num_lessons=2, get_params=None):
        '''Helper method to create a new project with lessons, and returns the GET response.'''
        #create project:
        resp = self.client.post(
            reverse('api:project-list'),
            json.dumps(self.project_object_to_add, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertIn(resp.status_code, xrange(200, 205))

        #add lessons:
        lessons = []
        for i in xrange(0,num_lessons):
            lesson = copy.deepcopy(self.lesson_object_to_add)
            lesson['order'] = i
            lessons.append(lesson)

        # post lessons in bulk using a single post request
        response = self.client.post(
            resp.data['self']  + 'lessons/',
            json.dumps(lessons, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertIn(response.status_code, xrange(200, 205))

        #get fresh data of the project:
        resp = self.client.get(resp.data['self'], get_params)
        self.assertEqual(resp.status_code, 200)

        return resp

    @should_check_action(actions_tested=('update',))
    def test_author_cant_skip_review_process(self):
        #make a project with no lessons:
        resp = self._get_new_project_with_lessons(0)

        api_obj_patch = {
            'publishMode': Project.PUBLISH_MODE_PUBLISHED,
        }

        api_obj = resp.data
        api_obj.update(api_obj_patch)

        resp2 = self.client.put(
            reverse('api:project-detail', kwargs={'pk': api_obj['id']}),
            json.dumps(api_obj, cls=DjangoJSONEncoder),
            content_type='application/json',
        )

        self.assertEqual(resp2.status_code, 403)

        resp3 = self.client.patch(
            reverse('api:project-detail', kwargs={'pk': api_obj['id']}),
            json.dumps(api_obj_patch, cls=DjangoJSONEncoder),
            content_type='application/json',
        )

        self.assertEqual(resp3.status_code, 403)


    @should_check_action(actions_tested=('update',))
    def test_cant_publish_without_lessons(self):
        #make a project with no lessons:
        resp = self._get_new_project_with_lessons(0)

        api_obj_patch = {
            'publishMode': Project.PUBLISH_MODE_REVIEW,
        }

        api_obj = resp.data
        api_obj.update(api_obj_patch)

        resp2 = self.client.put(
            reverse('api:project-detail', kwargs={'pk': api_obj['id']}),
            json.dumps(api_obj, cls=DjangoJSONEncoder),
            content_type='application/json',
        )

        self.assertEqual(resp2.status_code, 400)
        self.assertIn('publishErrors', resp2.data)
        self.assertIn('lessons', resp2.data['publishErrors'])

        resp3 = self.client.patch(
            reverse('api:project-detail', kwargs={'pk': api_obj['id']}),
            json.dumps(api_obj_patch, cls=DjangoJSONEncoder),
            content_type='application/json',
        )

        self.assertEqual(resp3.status_code, 400)

        self.assertIn('publishErrors', resp3.data)
        self.assertIn('lessons', resp3.data['publishErrors'])


    @unittest.skip('Reason: No required field for publish for lesson will ever be missed.')
    @should_check_action(actions_tested=('update',))
    def test_cant_publish_with_not_ready_lessons(self):
        #make a project with some lessons:
        resp = self._get_new_project_with_lessons()

        #change a lesson to be not ready for publish:
        resp2 = self.client.patch(
            resp.data['lessons'][0],
            json.dumps({'duration': None}, cls=DjangoJSONEncoder),
            content_type='application/json',
        )  #Note: This will always fail to save!
        self.assertEqual(resp2.status_code, 200)

        api_obj_patch = {
            'publishMode': Project.PUBLISH_MODE_PUBLISHED,
        }

        api_obj = resp.data
        api_obj.update(api_obj_patch)

        resp3 = self.client.put(
            api_obj['self'],
            json.dumps(api_obj, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp3.status_code, 400)
        self.assertIn('lessons', resp3.data)
        self.assertIn(resp2.data['id'], resp3.data['lessons'])
        self.assertIn('image', resp3.data['lessons'][resp2.data['id']])

        resp4 = self.client.patch(
            api_obj['self'],
            json.dumps(api_obj_patch, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp4.status_code, 400)
        self.assertIn('lessons', resp4.data)
        self.assertIn(resp2.data['id'], resp4.data['lessons'])
        self.assertIn('image', resp4.data['lessons'][resp2.data['id']])

    @should_check_action(actions_tested=('update',))
    def test_publish(self):
        #make a project with some lessons:
        resp = self._get_new_project_with_lessons()

        api_obj = resp.data
        api_obj['publishMode'] = Project.PUBLISH_MODE_REVIEW

        resp2 = self.client.put(
            reverse('api:project-detail', kwargs={'pk': api_obj['id']}),
            json.dumps(api_obj, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertIn(resp2.status_code, xrange(200,205))
        self.assertEqual(self.all_user_objects.get(id=api_obj['id']).publish_mode, Project.PUBLISH_MODE_REVIEW)

    @should_check_action(actions_tested=('update',))
    def test_publish_with_tinkercad_or_circuits_lesson_without_steps(self):
        #make a project with some lessons:
        resp = self._get_new_project_with_lessons()

        #add lessons that must have steps for publishing:
        lesson_apps_with_steps = [app for app,_ in Lesson.APPLICATIONS if app not in Lesson.STEPLESS_APPS]
        step_app_lessons_ids = []
        for lesson_app in lesson_apps_with_steps:
            lesson_resp = self.client.post(
                resp.data['self'] + 'lessons/',
                json.dumps({
                    'title': 'Lesson - ' + lesson_app,
                    'application': lesson_app,
                    'duration': 30,
                    'age': Project.AGE_15_PLUS,
                    'difficulty': Project.EASY_DIFFICULTY,
                    'license': Project.PUBLIC_DOMAIN,
                    'order': 0,
                }, cls=DjangoJSONEncoder),
                content_type='application/json',
            )
            self.assertEqual(lesson_resp.status_code, 201)
            step_app_lessons_ids.append(lesson_resp.data['id'])

        #publish the project:
        resp2 = self.client.patch(
            reverse('api:project-detail', kwargs={'pk': resp.data['id']}),
            json.dumps({
                'publishMode': Project.PUBLISH_MODE_REVIEW
            }, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp2.status_code, 400)

        for step_app_lesson_id in step_app_lessons_ids:
            self.assertIn(step_app_lesson_id, resp2.data['publishErrors']['lessons'])
            self.assertIn('stepsIds', resp2.data['publishErrors']['lessons'][step_app_lesson_id])

    @should_check_action(actions_tested=('update',))
    def test_publish_with_video_lesson_without_video(self):
        #make a project with some lessons:
        resp = self._get_new_project_with_lessons()

        #add video lesson:
        resp_video = self.client.post(
            resp.data['self'] + 'lessons/',
            json.dumps({
                'title': 'Video Lesson',
                'application': settings.LESSON_APPS['Video']['db_name'],
                'applicationBlob': {'video': {}},
                'duration': 30,
                'age': Project.AGE_15_PLUS,
                'difficulty': Project.EASY_DIFFICULTY,
                'license': Project.PUBLIC_DOMAIN,
                'order': 0,
            }, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp_video.status_code, 201)

        #publish the project:
        resp2 = self.client.patch(
            reverse('api:project-detail', kwargs={'pk': resp.data['id']}),
            json.dumps({
                'publishMode': Project.PUBLISH_MODE_REVIEW
            }, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp2.status_code, 400)

        self.assertIn(resp_video.data['id'], resp2.data['publishErrors']['lessons'])
        self.assertIn('applicationBlob', resp2.data['publishErrors']['lessons'][resp_video.data['id']])

    @should_check_action(actions_tested=('update',))
    def test_publish_with_instructables_lesson_without_url_id(self):
        #make a project with some lessons:
        resp = self._get_new_project_with_lessons()

        #add instructables lesson:
        resp_instructables = self.client.post(
            resp.data['self'] + 'lessons/',
            json.dumps({
                'title': 'Instructables Lesson',
                'application': settings.LESSON_APPS['Instructables']['db_name'],
                'applicationBlob': {'instructables': {}},
                'duration': 30,
                'age': Project.AGE_15_PLUS,
                'difficulty': Project.EASY_DIFFICULTY,
                'license': Project.PUBLIC_DOMAIN,
                'order': 0,
            }, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp_instructables.status_code, 201)

        #publish the project:
        resp2 = self.client.patch(
            reverse('api:project-detail', kwargs={'pk': resp.data['id']}),
            json.dumps({
                'publishMode': Project.PUBLISH_MODE_REVIEW
            }, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp2.status_code, 400)

        self.assertIn(resp_instructables.data['id'], resp2.data['publishErrors']['lessons'])
        self.assertIn('applicationBlob', resp2.data['publishErrors']['lessons'][resp_instructables.data['id']])

    @should_check_action(actions_tested=('update',))
    def test_disallow_change_project_from_published_to_unpublished(self):
        """Disallow to change project from published to unpublished"""
        project_obj = self.all_user_objects.filter(publish_mode=Project.PUBLISH_MODE_PUBLISHED)[0]
        project_obj_patch = {
            'publishMode': Project.PUBLISH_MODE_EDIT,
        }
        resp = self.client.patch(
            reverse(self.api_details_url, kwargs={'pk': project_obj.id}),
            project_obj_patch,
            'json'
        )
        self.assertIn(resp.status_code, [400, 403])

    def test_fail_to_delete_published_project(self):
        # make sure we have at least one published project
        self.assertTrue(self.all_user_objects.count()>0)
        # get pk for published project
        pk = self.all_user_objects[0].pk
        # delete lesson
        response = self.client.delete(reverse(self.api_details_url, kwargs={'pk': pk }))
        # verify deletion was not allowed 
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


    def test_get_list_is_enrolled_filter_true(self):
        '''
        Tests that the enrolled=true filter returns only projects
        that are taken by the user.
        '''

        # ProjectsInClassroomsTests overrides the default of "try all users".
        users = list(getattr(
            self,
            'users_with_get_permission',
            get_user_model().objects.all()
        ))
        if self.api_list_url == reverse('api:project-list'):  #add anonymous user for project-list view
            users += [None]
        truthy_values = ['1', 'True', 'trUE', 'asdfwer']

        for user in users:

            self.client.force_authenticate(user)

            objs_from_db = Project.objects.filter(
                id__in=ProjectState.objects.filter(
                    user=user,
                ).values('project')
            )

            first_response = None
            for idx, value in enumerate(truthy_values):
                resp = self.client.get(self.api_list_url, {
                    'user': 'current',
                    'enrolled': value,
                    'pageSize': objs_from_db.count(),
                })
                self.assertEqual(resp.status_code, 200)

                if idx == 0:
                    first_response = resp
                else:
                    self.assertEqual(resp.data.get('results'), first_response.data.get('results'))

            #test until here for annonymous user:
            if not user:
                continue

            # Make sure we get the correct number of objects.
            self.assertEqual(first_response.data['count'], objs_from_db.count())
            self.compare_db_obj_list_with_api(objs_from_db, first_response.data['results'])

    def test_get_list_is_enrolled_filter_false(self):
        '''
        Tests that the stateIsCompleted=false filter returns only projects
        that are taken by the user and are NOT completed.
        '''

        # ProjectsInClassroomsTests overrides the default of "try all users".
        users = list(getattr(
            self,
            'users_with_get_permission',
            get_user_model().objects.all()
        ))
        if self.api_list_url == reverse('api:project-list'):  #add anonymous user for project-list view
            users += [None]
        falsey_values = ['0', 'False', 'false', 'fALSe']

        for user in users:

            self.client.force_authenticate(user)

            objs_from_db = Project.objects.exclude(
                id__in=ProjectState.objects.filter(
                    user=user,
                ).values('project')
            )

            first_response = None
            for idx, value in enumerate(falsey_values):
                resp = self.client.get(self.api_list_url, {
                    'user': 'current',
                    'enrolled': value,
                    'pageSize': objs_from_db.count(),  #note that probably less projects will be returned, since projects list is filtered more
                })
                self.assertEqual(resp.status_code, 200)

                if idx == 0:
                    first_response = resp
                else:
                    self.assertEqual(resp.data, first_response.data)

            #test until here for annonymous user:
            if not user:
                continue

            #Make that all projects returned are not enrolled:
            for proj in first_response.data['results']:
                self.assertFalse(proj['enrolled'])

    def test_get_list_is_completed_filter_true(self):
        '''
        Tests that the stateIsCompleted=true filter returns only projects
        that are taken by the user and are completed.
        '''

        # ProjectsInClassroomsTests overrides the default of "try all users".
        users = list(getattr(
            self,
            'users_with_get_permission',
            get_user_model().objects.all()
        ))
        if self.api_list_url == reverse('api:project-list'):  #add anonymous user for project-list view
            users += [None]
        truthy_values = ['1', 'True', 'trUE', 'asdfwer']

        self.assertGreaterEqual(
            ProjectState.objects.filter(is_completed=True).count(),
            2,
        )

        for user in users:

            self.client.force_authenticate(user)

            objs_from_db = Project.objects.filter(
                id__in=ProjectState.objects.filter(
                    user=user,
                    is_completed=True
                ).values('project')
            )

            first_response = None
            for idx, value in enumerate(truthy_values):
                resp = self.client.get(self.api_list_url, {
                    'user': 'current',
                    'enrolled': 'true',
                    'stateIsCompleted': value,
                    'pageSize': objs_from_db.count(),
                })
                self.assertEqual(resp.status_code, 200)

                if idx == 0:
                    first_response = resp
                else:
                    self.assertEqual(resp.data, first_response.data)

            #test until here for annonymous user:
            if not user:
                continue

            # Make sure we get the correct number of objects.
            self.assertEqual(first_response.data['count'], objs_from_db.count())
            self.compare_db_obj_list_with_api(objs_from_db, first_response.data['results'])

    def test_get_list_is_completed_filter_false(self):
        '''
        Tests that the stateIsCompleted=false filter returns only projects
        that are taken by the user and are NOT completed.
        '''

        # ProjectsInClassroomsTests overrides the default of "try all users".
        users = list(getattr(
            self,
            'users_with_get_permission',
            get_user_model().objects.all()
        ))
        if self.api_list_url == reverse('api:project-list'):  #add anonymous user for project-list view
            users += [None]
        falsey_values = ['0', 'False', 'false', 'fALSe']

        self.assertGreaterEqual(
            ProjectState.objects.filter(is_completed=False).count(),
            2,
        )

        for user in users:

            self.client.force_authenticate(user)

            objs_from_db = Project.objects.filter(
                id__in=ProjectState.objects.filter(
                    user=user,
                    is_completed=False
                ).values('project')
            )

            first_response = None
            for idx, value in enumerate(falsey_values):
                resp = self.client.get(self.api_list_url, {
                    'user': 'current',
                    'enrolled': 'true',
                    'stateIsCompleted': value,
                    'pageSize': objs_from_db.count(),
                })
                self.assertEqual(resp.status_code, 200)

                if idx == 0:
                    first_response = resp
                else:
                    self.assertEqual(resp.data.get('results'), first_response.data.get('results'))

            #test until here for annonymous user:
            if not user:
                continue

            # Make sure we get the correct number of objects.
            self.assertEqual(first_response.data['count'], objs_from_db.count())
            self.compare_db_obj_list_with_api(objs_from_db, first_response.data['results'])

    def test_get_list_of_projects_for_collaboration(self):
        """Test that ?forCollaboration filters only projects that the user is the owner or delegate of the owner."""
        delegate_user = get_user_model().objects.exclude(pk=self.global_user.pk, pk__in=self.global_user.delegates.all()).first()
        owner_delegate = OwnerDelegate.objects.create(owner=self.global_user, user=delegate_user)

        # Make project to delegate user:
        resp = self._get_new_project_with_lessons()
        project_obj = Project.objects.get(pk=resp.data['id'])
        project_obj.owner = delegate_user
        project_obj.save()

        resp2 = self.client.get(self.api_list_url + '?forCollaboration=true')
        self.assertEqual(resp2.status_code, 200)

        # Check that delegate user gets all projects
        self.assertEqual(
            resp2.data['count'],
            self.all_user_objects.filter(
                owner__in=[delegate_user]+list(delegate_user.delegators.values_list('id', flat=True))
            ).count()
        )

        # Clean
        owner_delegate.delete()

    def test_user_app_can_get_unpublished_project(self):

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

            # Get an unpublished project that doesn't belong to the user 
            # (user is new, so 2nd requirement is trivial).
            app_project = Project.objects.filter(
                publish_mode=Project.PUBLISH_MODE_EDIT
            ).first()

            # Check that the project is accessible by the user.
            resp = self.client.get(reverse(
                self.api_details_url, kwargs={'pk': app_project.id}
            ))
            self.assertEqual(resp.status_code, status.HTTP_200_OK)

            # Delete the user from the Database.
            user.delete()

    def test_user_app_cant_edit_unpublished_project(self):

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

            # Get an unpublished project that doesn't belong to the user 
            # (user is new, so 2nd requirement is trivial).
            app_project = Project.objects.filter(
                publish_mode=Project.PUBLISH_MODE_EDIT
            ).first()

            # Check that the project is not editable by the user.
            resp = self.client.patch(
                reverse(self.api_details_url, kwargs={'pk': app_project.id}),
                json.dumps({'title': app_project.title + '.'}, cls=DjangoJSONEncoder),
                content_type='application/json',
            )
            self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

            # Restore database
            user.delete()

    def test_idlist_filter_maintains_order(self):
        '''
        Test that project list, filtered by idList returns in the order it was requested
        '''
        idList = [3,1,2]

        response = self.client.get(
            self.api_list_url,
            {'idList': ','.join([str(i) for i in idList]) },
            content_type='application/json',
        )

        returned_ids = [x['id'] for x in response.data['results'] ]
        self.assertEqual(idList, returned_ids)


    def test_get_projects_queries_num(self):
        """Test that number of queries doesn't sky rocket"""

        self.assertRangeQueries(
            xrange(1,15), lambda: self.client.get(self.api_list_url)
        )

    def test_get_projects_with_lessons_queries_num(self):
        """Test that number of queries doesn't sky rocket when embedding lessons"""

        self.assertRangeQueries(
            xrange(1,15),
            lambda: self.client.get(self.api_list_url, {'embed': 'lessons'}),
        )

    def get_list_with_min_size(self, min_list_size, for_edit=False):
        user_objects = self.all_user_objects_for_edit if for_edit and self.all_user_objects_for_edit else self.all_user_objects
        return user_objects.annotate(**{
            '%s_num' % self.embedded_obj_p: Count(self.embedded_obj_p)
        }).filter(**{
            '%s_num__gte' % self.embedded_obj_p: min_list_size
        })

    def test_cant_add_or_remove_object_to_embedded_list(self):
        '''
        Make sure its NOT possible to add or remove a lesson to/from the lessons list of a project.
        '''

        # Get a list with at least 2 items.
        obj = self.get_list_with_min_size(2, for_edit=True)[0]

        resp = self.client.get(
            reverse(self.api_details_url, kwargs={'pk': obj.id}),
            {'embed': self.embedded_list_ids}
        )

        # Add object to list:
        obj_to_put = copy.deepcopy(resp.data)
        list_ids = obj_to_put[self.embedded_list_ids]

        # Get an ID of an object that's not in the list.
        obj_id = self.embedded_model.objects.exclude(
            id__in=getattr(
                obj, self.embedded_obj_p
            ).all().values_list('id', flat=True)
        ).filter(project__publish_mode=Project.PUBLISH_MODE_PUBLISHED)[0].id

        self.assertNotIn(obj_id, list_ids)

        # Insert the object to the middle of the list.
        list_ids.insert(int(len(list_ids) / 2), obj_id)

        resp1 = self.client.put(
            obj_to_put['self'] + '?embed=%s' % self.embedded_list_ids,
            json.dumps(obj_to_put, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp1.status_code, 400)

        # Remove object from list:
        obj_to_put = copy.deepcopy(resp.data)
        list_ids = obj_to_put[self.embedded_list_ids]

        # Remove an object from the middle of the list.
        list_ids.remove(list_ids[int(len(list_ids) / 2)])

        resp2 = self.client.put(
            obj_to_put['self'] + '?embed=%s' % self.embedded_list_ids,
            json.dumps(obj_to_put, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp2.status_code, 400)


    def test_change_embedded_list_order(self):
        '''
        Change the order of a list in an object when using the ?embed= parameter
        '''

        ids_list_name = self.embedded_list_ids

        # Get a list of 2 or more.
        obj_id = self.get_list_with_min_size(2, for_edit=True)[0].id

        resp = self.client.get(reverse(
            self.api_details_url, kwargs={'pk': obj_id}),
            {'embed': ids_list_name}
        )
        self.assertGreater(len(resp.data[ids_list_name]), 1)

        api_obj = resp.data

        # Swap the last and first items in the list
        ids_list = api_obj[ids_list_name]
        ids_list[0], ids_list[-1] = ids_list[-1], ids_list[0]

        resp = self.client.put(
            api_obj['self'] + '?embed=%s' % ids_list_name,
            json.dumps(api_obj, cls=DjangoJSONEncoder),
            content_type='application/json'
        )

        self.assertIn(resp.status_code, range(200, 205))

        # Check the IDs list
        #TODO: When counter field available, assert equal counts.
        self.assertEqual(len(api_obj[ids_list_name]), len(resp.data[ids_list_name]))
        for idx, embedded_obj_id in enumerate(resp.data[ids_list_name]):

            self.assertEqual(embedded_obj_id, api_obj[ids_list_name][idx])

            # Check that objects' order has changed
            # self.assertEqual(embedded_obj_id, resp.data[self.embedded_obj_p][idx]['id'])

        # Check that another GET operation returns the new order
        resp2 = self.client.get(reverse(
            self.api_details_url, kwargs={'pk': obj_id}),
            {'embed': self.embedded_list_ids}
        )
        self.assertGreater(len(resp2.data[self.embedded_list_ids]), 0)
        self.assertEqual(resp.data[ids_list_name], resp2.data[ids_list_name])
        # self.assertEqual(resp.data[self.embedded_obj_p], resp2.data[self.embedded_obj_p])


    def test_change_list_order_in_object(self):
        '''
        Change the order of the list in an object when NOT using the ?embed=
        parameter.
        '''

        ids_list_name = self.embedded_list_ids

        # Get a list longer than 1.
        obj_id = self.get_list_with_min_size(2, for_edit=True)[0].id

        resp = self.client.get(reverse(self.api_details_url, kwargs={'pk': obj_id}), {'embed': ids_list_name})
        self.assertGreater(len(resp.data[ids_list_name]), 0)

        api_obj = resp.data

        # Swap the last and first objects in the list
        ids_list = api_obj[ids_list_name]
        ids_list[0], ids_list[-1] = ids_list[-1], ids_list[0]

        resp = self.client.put(
            api_obj['self'] + '?embed=%s' % ids_list_name,
            json.dumps(api_obj, cls=DjangoJSONEncoder),
            content_type='application/json'
        )

        self.assertIn(resp.status_code, range(200, 205))

        # Check the list of IDs
        #TODO: When counter field available, assert equal counts.
        self.assertEqual(len(api_obj[ids_list_name]), len(resp.data[ids_list_name]))
        for idx, embedded_obj_id in enumerate(resp.data[ids_list_name]):

            self.assertEqual(embedded_obj_id, api_obj[ids_list_name][idx])

            # # Check that objects' order has changed
            # self.assertIn(reverse(
            #     'api:project-%s-detail' % self.embedded_obj_s,
            #     kwargs={'project_pk': obj_id, 'pk': embedded_obj_id}
            # ), resp.data[self.embedded_obj_p][idx])

        # Check that another GET operation returns the new order
        resp2 = self.client.get(reverse(self.api_details_url, kwargs={'pk': obj_id}), {'embed': ids_list_name})
        self.assertGreater(len(resp2.data[ids_list_name]), 0)
        self.assertEqual(resp.data[ids_list_name], resp2.data[ids_list_name])
        # self.assertEqual(resp.data[self.embedded_obj_p], resp2.data[self.embedded_obj_p])

    def test_put_returns_400_embedded_list_not_affected(self):
        '''
        This is a test for #24: When an existing object "save" operation failed
        all of the object's lessons were deleted from the DB :-(
        '''

        # Get a list with at least 3 items.
        obj = self.get_list_with_min_size(3, for_edit=True)[0]

        list_len = getattr(obj, self.embedded_obj_p).all().count()
        self.assertGreaterEqual(list_len, 3)

        resp = self.client.get(reverse(self.api_details_url, kwargs={'pk': obj.id}))

        # This combination of parameters should return a 400
        resp.data['title'] = ''
        resp.data['duration'] = 0

        resp1 = self.client.put(
            resp.data['self'],
            json.dumps(resp.data, cls=DjangoJSONEncoder),
            content_type='application/json'
        )

        # Make sure that the PUT operation failed.
        self.assertEqual(resp1.status_code, 400)

        obj_after = (self.all_user_objects_for_edit if self.all_user_objects_for_edit else self.all_user_objects).get(id=obj.id)

        list_len_after = getattr(obj_after, self.embedded_obj_p).all().count()
        self.assertGreaterEqual(list_len_after, 3)
        self.assertEqual(list_len, list_len_after)
        self.assertListEqual(
            list(getattr(obj, self.embedded_obj_p).all()),
            list(getattr(obj_after, self.embedded_obj_p).all())
        )

    def test_put_embedded_without_attribute_list_not_affected(self):
        '''
        Tests that when embedded attribute is omitted, list is not affected
        '''

        # Get a list with at least 3 items.
        obj = self.get_list_with_min_size(3, for_edit=True)[0]

        list_len = getattr(obj, self.embedded_obj_p).all().count()
        self.assertGreaterEqual(list_len, 3)

        resp = self.client.get(reverse(self.api_details_url, kwargs={'pk': obj.id}), {'embed': self.embedded_list_ids})

        # remove embedded attribute:
        del resp.data[self.embedded_list_ids]

        resp1 = self.client.put(
            resp.data['self'] + '?embed=%s'%self.embedded_list_ids,
            json.dumps(resp.data, cls=DjangoJSONEncoder),
            content_type='application/json'
        )

        self.assertIn(resp1.status_code, range(200, 205))

        obj_after = (self.all_user_objects_for_edit if self.all_user_objects_for_edit else self.all_user_objects).get(id=obj.id)

        list_len_after = getattr(obj_after, self.embedded_obj_p).all().count()
        self.assertGreaterEqual(list_len_after, 3)
        self.assertEqual(list_len, list_len_after)
        self.assertListEqual(
            list(getattr(obj, self.embedded_obj_p).all()),
            list(getattr(obj_after, self.embedded_obj_p).all())
        )

        self.assertListEqual(
            resp1.data[self.embedded_list_ids],
            list(getattr(obj_after, self.embedded_obj_p).values_list('id', flat=True))
        )

    def test_inline_fields_dont_duplicate(self):
        super(ProjectTests, self).test_inline_fields_dont_duplicate(self.all_user_objects_for_edit)



    @should_check_action(actions_tested=('update',))
    def test_published_projects_not_editable_on_api(self):
        '''Test that published projects cannot be edited using the api '''
        # create project
        obj = self._get_new_project_with_lessons().data
        # edit project and update server
        obj['duration'] = 50
        response = self.client.put(obj['self'],
            json.dumps(obj, cls=DjangoJSONEncoder),
            content_type='application/json'
        )
        # verify update was accepted
        self.assertEqual(response.status_code,200)

        # publish project
        project_obj = Project.objects.get(id=obj['id'])
        project_obj.publish_mode = Project.PUBLISH_MODE_PUBLISHED
        project_obj.save()

        # fail to edit project
        obj['duration'] = 60
        response = self.client.put(obj['self'],
            json.dumps(obj, cls=DjangoJSONEncoder),
            content_type='application/json'
        )
        # verify update was accepted
        self.assertEqual(response.status_code,403)


    def test_project_counters(self):
        """
        Make sure the project counters are correct.
        """
        #build counters:
        management.call_command('rebuild_counters')

        self.client.force_authenticate(self.global_user)
        data = self.client.get(self.api_list_url).data['results']

        for project_data in data:
            project_obj = Project.objects.get(id=project_data['id'])
            self.assertEqual(project_data['numberOfLessons'], project_obj.lessons.count())
            self.assertEqual(project_data['numberOfStudents'], project_obj.registrations.count())

    # isPurchased query parameter
    # ###########################

    def test_is_purchased_returns_purchased_projects(self):

        user1 = get_user_model()(
            is_approved=True,
            name='user 1',
            short_name='u 1',
            oxygen_id='1234',
            is_child=False,
            avatar='http://placekitten.com/300/300/',
            member_id='4321',
            email='o@o.com',
        )
        user1.save()
        user2 = get_user_model()(
            is_approved=True,
            name='user 2',
            short_name='u 2',
            oxygen_id='1235',
            is_child=False,
            avatar='http://placekitten.com/300/300/',
            member_id='5321',
            email='o@o.com',
        )
        user2.save()
        locked_projects = Project.objects.filter(lock=1, publish_mode=Project.PUBLISH_MODE_PUBLISHED)
        locked_project1 = locked_projects[0]
        locked_project2 = locked_projects[1]

        p1 = Purchase(user=user1, project=locked_project1, permission=Purchase.TEACH_PERM)
        p2 = Purchase(user=user1, project=locked_project2, permission=Purchase.VIEW_PERM)
        p3 = Purchase(user=user2, project=locked_project2, permission=Purchase.TEACH_PERM)
        p1.save()
        p2.save()
        p3.save()

        self.client.force_authenticate(user1)

        resp_purchased = self.client.get(reverse('api:project-list') + '?isPurchased=true')
        resp_not_purchased = self.client.get(reverse('api:project-list') + '?isPurchased=false')
        resp_all = self.client.get(reverse('api:project-list'))

        self.assertEqual(resp_purchased.status_code, 200)
        self.assertEqual(resp_not_purchased.status_code, 200)
        self.assertEqual(resp_all.status_code, 200)

        self.assertEqual(resp_all.data['count'], resp_purchased.data['count'] + resp_not_purchased.data['count'])

        self.assertIn(locked_project1.id, [p['id'] for p in resp_purchased.data['results']])
        self.assertNotIn(locked_project2.id, [p['id'] for p in resp_purchased.data['results']])
        self.assertNotIn(locked_project1.id, [p['id'] for p in resp_not_purchased.data['results']])

        p1.delete()
        p2.delete()
        p3.delete()

        user1.delete()
        user2.delete()


    # Project author
    # ##############

    def test_owner_can_set_author_to_any_delegate(self):
        owner = self.global_user
        project = Project.objects.filter(publish_mode=Project.PUBLISH_MODE_EDIT, owner=owner).first()
        new_author = get_user_model().objects.exclude(pk=self.global_user.pk).filter(is_child=False).first()

        # New author not related to project owner - not allowed:

        resp = self.client.patch(
            reverse(self.api_details_url, kwargs={'pk': project.id}),
            data=json.dumps({
                'author': {'id': new_author.id},
            }, cls=DjangoJSONEncoder),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('author', resp.data)

        # New author is a delegate of project owner - not allowed:

        owner_delegate_obj = OwnerDelegate.objects.create(owner=self.global_user, user=new_author)
        resp = self.client.patch(
            reverse(self.api_details_url, kwargs={'pk': project.id}),
            data=json.dumps({
                'author': {'id': new_author.id},
            }, cls=DjangoJSONEncoder),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('author', resp.data)
        owner_delegate_obj.delete()

        # add new author user as project owner's delegator:

        owner_delegate_obj = OwnerDelegate.objects.create(owner=new_author, user=self.global_user)
        resp = self.client.patch(
            reverse(self.api_details_url, kwargs={'pk': project.id}),
            data=json.dumps({
                'author': {'id': new_author.id},
            }, cls=DjangoJSONEncoder),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['author']['id'], new_author.id)
        owner_delegate_obj.delete()
        project.owner = self.global_user
        project.save()

        # Project owner is superuser - can change to any adult user:

        self.global_user.is_superuser = True
        self.global_user.save()

        resp = self.client.patch(
            reverse(self.api_details_url, kwargs={'pk': project.id}),
            data=json.dumps({
                'author': {'id': new_author.id},
            }, cls=DjangoJSONEncoder),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['author']['id'], new_author.id)
        project.owner = self.global_user
        project.save()

        owner_delegate_obj = OwnerDelegate.objects.create(owner=new_author, user=self.global_user)
        resp = self.client.patch(
            reverse(self.api_details_url, kwargs={'pk': project.id}),
            data=json.dumps({
                'author': {'id': get_user_model().objects.exclude(pk=self.global_user.pk).filter(is_child=True).first().id},
            }, cls=DjangoJSONEncoder),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('author', resp.data)
        owner_delegate_obj.delete()

        self.global_user.is_superuser = False
        self.global_user.save()


    def test_create_new_project_in_edit_mode_only(self):
        resp = self.client.post(
            reverse('api:project-list'),
            json.dumps(self.project_object_to_add, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertIn(resp.status_code, xrange(200, 205))
        self.assertEqual(resp.data['publishMode'], Project.PUBLISH_MODE_EDIT)

        resp2 = self.client.get(resp.data['self'])
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.data['publishMode'], Project.PUBLISH_MODE_EDIT)

        # Fail to create project in other mode:
        obj_to_post = copy.deepcopy(self.project_object_to_add)
        obj_to_post.update({
            'publishMode': Project.PUBLISH_MODE_PUBLISHED,
        })
        resp = self.client.post(
            reverse('api:project-list'),
            json.dumps(obj_to_post, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('publishMode', resp.data)


    def test_projects_extra_lessons_init_validation(self):
        resp = self._get_new_project_with_lessons(4)
        project_self = resp.data['self']
        project_obj = Project.objects.get(pk=resp.data['id'])
        project_lessons = list(project_obj.lessons.all())
        tinkercad_lessons = project_lessons[:2]
        circuits_lessons = project_lessons[2:]
        for l in tinkercad_lessons:
            l.application = settings.LESSON_APPS['Tinkercad']['db_name']
            l.save()
        for l in circuits_lessons:
            l.application = settings.LESSON_APPS['Circuits']['db_name']
            l.save()

        # Validate invalid lesson id:
        resp = self.client.patch(
            project_self,
            json.dumps({
                'extra': {
                    'lessonsInit': [{
                        'lessonsIds': ['invalid'],
                    }]
                }
            }, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('extra', resp.data)
        self.assertIn('lessonsInit', resp.data['extra'])

        # Validate lessonsIds is not a list:
        resp = self.client.patch(
            project_self,
            json.dumps({
                'extra': {
                    'lessonsInit': [{
                        'lessonsIds': "not a list",
                    }]
                }
            }, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('extra', resp.data)
        self.assertIn('lessonsInit', resp.data['extra'])

        # Validate lesson not in project:
        resp = self.client.patch(
            project_self,
            json.dumps({
                'extra': {
                    'lessonsInit': [{
                        'lessonsIds': [9999999],
                    }]
                }
            }, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('extra', resp.data)
        self.assertIn('lessonsInit', resp.data['extra'])

        # Validate group of lessons not of the same type:
        resp = self.client.patch(
            project_self,
            json.dumps({
                'extra': {
                    'lessonsInit': [{
                        'lessonsIds': [tinkercad_lessons[0].id, circuits_lessons[0].id],
                    }]
                }
            }, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('extra', resp.data)
        self.assertIn('lessonsInit', resp.data['extra'])

        # Group some lessons with no init canvas id:
        extra_data = {
            'lessonsInit': [{
                'lessonsIds': [tinkercad_lessons[0].id, tinkercad_lessons[1].id],
                'application': 'BLAH',  #should be truncated
                'custom_key': 'Keep Me!'  #should be kept for the lessons group
            }]
        }
        resp = self.client.patch(
            project_self,
            json.dumps({
                'extra': extra_data
            }, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(resp.data['extra'])
        self.assertEqual(len(resp.data['extra']['lessonsInit']), 1)
        self.assertEqual(resp.data['extra']['lessonsInit'][0]['lessonsIds'], extra_data['lessonsInit'][0]['lessonsIds'])
        self.assertEqual(resp.data['extra']['lessonsInit'][0]['application'], tinkercad_lessons[0].application)
        self.assertNotIn('initCanvasId', resp.data['extra']['lessonsInit'][0])
        self.assertEqual(resp.data['extra']['lessonsInit'][0]['custom_key'], extra_data['lessonsInit'][0]['custom_key'])

        # Group some lessons with init canvas id - remove duplicates from same group:
        extra_data = {
            'lessonsInit': [{
                'lessonsIds': [x.id for x in tinkercad_lessons] + [tinkercad_lessons[0].id],
                'initCanvasId': 'A1B2C3',
            }]
        }
        resp = self.client.patch(
            project_self,
            json.dumps({
                'extra': extra_data
            }, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(resp.data['extra'])
        self.assertEqual(len(resp.data['extra']['lessonsInit']), 1)
        self.assertEqual(resp.data['extra']['lessonsInit'][0]['lessonsIds'], [x.id for x in tinkercad_lessons])
        self.assertEqual(resp.data['extra']['lessonsInit'][0]['application'], tinkercad_lessons[0].application)
        self.assertEqual(resp.data['extra']['lessonsInit'][0]['initCanvasId'], extra_data['lessonsInit'][0]['initCanvasId'])

        # Group single lesson with canvas id:
        extra_data = {
            'lessonsInit': [{
                'lessonsIds': [tinkercad_lessons[0].id],
                'initCanvasId': 'A1B2C3',
            }]
        }
        resp = self.client.patch(
            project_self,
            json.dumps({
                'extra': extra_data
            }, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(resp.data['extra'])
        self.assertEqual(len(resp.data['extra']['lessonsInit']), 1)
        self.assertEqual(resp.data['extra']['lessonsInit'][0]['lessonsIds'], extra_data['lessonsInit'][0]['lessonsIds'])
        self.assertEqual(resp.data['extra']['lessonsInit'][0]['application'], tinkercad_lessons[0].application)
        self.assertEqual(resp.data['extra']['lessonsInit'][0]['initCanvasId'], extra_data['lessonsInit'][0]['initCanvasId'])

        # Group with single lesson with no canvas id is omitted, and empty lessonsInit is omitted too - without anything else in extra:
        extra_data = {
            'lessonsInit': [{
                'lessonsIds': [tinkercad_lessons[0].id],
                'custom_key': 'If group is omitted, this will be lost too!'
            }]
        }
        resp = self.client.patch(
            project_self,
            json.dumps({
                'extra': extra_data
            }, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data['extra'], None)

        # Group with single lesson with no canvas id is omitted, and empty lessonsInit is omitted too - with something else in extra:
        extra_data = {
            'lessonsInit': [{
                'lessonsIds': [tinkercad_lessons[0].id],
                'custom_key': 'If group is omitted, this will be lost too!'
            }],
            'specialData': {
                'key1': 'I can have anything here!',
                'key2': ['A', 100],
            }
        }
        resp = self.client.patch(
            project_self,
            json.dumps({
                'extra': extra_data
            }, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(resp.data['extra'])
        self.assertNotIn('lessonsInit', resp.data['extra'])
        self.assertDictEqual(resp.data['extra']['specialData'], extra_data['specialData'])

        # Have some lessons groups in lessonsInit:
        extra_data = {
            'lessonsInit': [{
                'lessonsIds': [tinkercad_lessons[0].id],
                'initCanvasId': 'A1B2C3',
            }, {
                'lessonsIds': [circuits_lessons[0].id, circuits_lessons[1].id],
                'initCanvasId': 'CircuitsCanvas-5391',
            }]
        }
        resp = self.client.patch(
            project_self,
            json.dumps({
                'extra': extra_data
            }, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(resp.data['extra'])
        self.assertEqual(len(resp.data['extra']['lessonsInit']), 2)
        self.assertEqual(resp.data['extra']['lessonsInit'][0]['lessonsIds'], extra_data['lessonsInit'][0]['lessonsIds'])
        self.assertEqual(resp.data['extra']['lessonsInit'][0]['application'], tinkercad_lessons[0].application)
        self.assertEqual(resp.data['extra']['lessonsInit'][0]['initCanvasId'], extra_data['lessonsInit'][0]['initCanvasId'])
        self.assertEqual(resp.data['extra']['lessonsInit'][1]['lessonsIds'], extra_data['lessonsInit'][1]['lessonsIds'])
        self.assertEqual(resp.data['extra']['lessonsInit'][1]['application'], circuits_lessons[0].application)
        self.assertEqual(resp.data['extra']['lessonsInit'][1]['initCanvasId'], extra_data['lessonsInit'][1]['initCanvasId'])


    def test_projects_list_non_searchable(self):
        user = self.global_user
        user_all_projects = self.all_user_objects
        self.assertEqual(user_all_projects.count(), user_all_projects.filter(is_searchable=True).count(), msg='Assumed starting when all projects are searchable.')
        self.client.force_authenticate(user)

        old_num_user_all_projects = user_all_projects.count()

        resp = self.client.get(self.api_list_url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], old_num_user_all_projects)

        # Hide project of user and project not of user
        hidden_project_1 = user_all_projects.filter(owner=user)[0]
        hidden_project_1.is_searchable = False
        hidden_project_1.save()
        hidden_project_2 = user_all_projects.exclude(
            Q(owner=user) | Q(owner__in=user.delegators.all()) | Q(owner__in=user.children.all()) |
            Q(pk__in=user.purchases.values('project'))
        )[0]
        hidden_project_2.is_searchable = False
        hidden_project_2.save()

        # Check projects default list
        num_user_all_projects = user_all_projects.count()
        # make sure that hidden project that is not of the user is not in the default list:
        self.assertEqual(num_user_all_projects, old_num_user_all_projects-1)
        user_all_projects_ids = [x.id for x in user_all_projects]
        self.assertIn(hidden_project_1.id, user_all_projects_ids)
        self.assertNotIn(hidden_project_2.id, user_all_projects_ids)

        # GET /projects/
        resp = self.client.get(self.api_list_url, {'pageSize': old_num_user_all_projects})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], num_user_all_projects)
        self.assertSetEqual(
            set([x['id'] for x in resp.data['results']]),
            set([x.id for x in user_all_projects])
        )

    def test_project_detail_non_searchable(self):
        user = self.global_user
        self.client.force_authenticate(user)

        # Get project, hide it, and check that it is still accessible explicitly for details:
        hidden_project = self.all_user_objects.exclude(
            Q(owner=user) | Q(owner__in=user.delegators.all()) | Q(owner__in=user.children.all()) |
            Q(pk__in=user.purchases.values('project'))
        )[0]

        resp = self.client.get(self.get_api_details_url(hidden_project))
        self.assertEqual(resp.status_code, 200)

        hidden_project.is_searchable = False
        hidden_project.save()
        resp = self.client.get(self.get_api_details_url(hidden_project))
        self.assertEqual(resp.status_code, 200)

    #IMPORTANT NOTE:
    #   When enable in FilterAllowedMixin to include projects published and purchased
    #   (even not searchable) then do not skip the following test:
    @unittest.skip('Not including published non searchable projects to list.')
    def test_projects_list_non_searchable_and_purchased(self):
        user = self.global_user
        user_all_projects = self.all_user_objects
        self.assertEqual(user_all_projects.count(), user_all_projects.filter(is_searchable=True).count(), msg='Assumed starting when all projects are searchable.')
        self.client.force_authenticate(user)

        old_num_user_all_projects = user_all_projects.count()

        resp = self.client.get(self.api_list_url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], old_num_user_all_projects)

        # Hide a searchable project not owned or purchased by the user
        hidden_project = user_all_projects.exclude(
            Q(owner=user) | Q(owner__in=user.delegators.all()) | Q(owner__in=user.children.all()) |
            Q(pk__in=user.purchases.values('project'))
        )[0]
        hidden_project.is_searchable = False
        hidden_project.save()

        # Check projects default list
        num_user_all_projects = user_all_projects.count()
        # make sure that hidden project that is not of the user is not in the default list:
        self.assertEqual(num_user_all_projects, old_num_user_all_projects-1)
        user_all_projects_ids = [x.id for x in user_all_projects]
        self.assertNotIn(hidden_project.id, user_all_projects_ids)

        # GET /projects/
        resp = self.client.get(self.api_list_url, {'pageSize': old_num_user_all_projects})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], num_user_all_projects)
        self.assertSetEqual(
            set([x['id'] for x in resp.data['results']]),
            set([x.id for x in user_all_projects])
        )

        # Make the project bundled and purchase it by the user
        purchased_hidden_project = hidden_project
        purchased_hidden_project.lock = Project.BUNDLED
        purchased_hidden_project.save()
        Purchase.objects.get_or_create(project=purchased_hidden_project, user=user, defaults={'permission': Purchase.VIEW_PERM})

        # Check projects default list
        user_all_projects = self.all_user_objects.all()  #to clear cached queryset
        num_user_all_projects = user_all_projects.count()
        # make sure that hidden purchased project is in the default list:
        self.assertEqual(num_user_all_projects, old_num_user_all_projects)
        user_all_projects_ids = [x.id for x in user_all_projects]
        self.assertIn(purchased_hidden_project.id, user_all_projects_ids)

        # GET /projects/
        resp = self.client.get(self.api_list_url, {'pageSize': old_num_user_all_projects})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], num_user_all_projects)
        self.assertSetEqual(
            set([x['id'] for x in resp.data['results']]),
            set([x.id for x in user_all_projects])
        )
