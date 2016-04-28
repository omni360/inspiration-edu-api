import re
import json
import redis, fakeredis
from django_redis import get_redis_connection
import httpretty
import unittest
import functools
import urllib

from collections import Counter

from django.test import override_settings
from django.core.urlresolvers import reverse
from django.conf import settings
from django.db.models import Count, Sum, Q
from django.contrib.auth import get_user_model
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.dateparse import parse_datetime

from rest_framework import serializers
from rest_framework.test import APITestCase as DRFTestCase
from rest_framework.authtoken.models import Token

from .mock_oxygen import MockOxygen
from .utils.mock_spark_drive_api import MockSparkDriveApi
from .base_test_case import BaseTestCase

from ..models import IgniteUser, Project, ChildGuardian, Review, ProjectState, LessonState, ClassroomState
from ..serializers import FullUserSerializer
from ..views.authentication import RedisAuthentication
from ..views import VerifyAdulthood
from ..auth.views import ObtainApiAuthToken


def patch_redis(test):
    '''
    httpretty has a problem with Redis. It somehow causes Redis to hang when it
    operates. You can read more about it here:
    https://github.com/gabrielfalcao/HTTPretty/issues/113

    The (ugly) workaround that we have for this problem is that we wrap test
    functions that use both httpretty and redis with this decorator. The 
    decorator disables httpretty before every redis operation and re-enables 
    it afterwards.
    '''

    def decorate_class(klass):
        for attr in dir(klass):
            if not attr.startswith('test_'):
                continue

            attr_value = getattr(klass, attr)
            if not hasattr(attr_value, "__call__"):
                continue

            setattr(klass, attr, decorate_callable(attr_value))
        return klass

    def decorate_callable(test):
        @functools.wraps(test)
        def wrapper(*args, **kw):
            # ignore this patch if when using a redis mock
            if redis.StrictRedis is fakeredis.FakeStrictRedis:
                return wrapper

            orig_execute_command = redis.StrictRedis.execute_command

            def patched_orig_execute_command(self, *args, **kwargs):
                httpretty.disable()
                res = orig_execute_command(self,*args,**kwargs)
                httpretty.enable()
                return res

            redis.StrictRedis.execute_command = patched_orig_execute_command
            try:
                return test(*args, **kw)
            finally:
                redis.StrictRedis.execute_command = orig_execute_command
                
        return wrapper

    if isinstance(test, type):
        return decorate_class(test)
    return decorate_callable(test)


@override_settings(DISABLE_SENDING_CELERY_EMAILS=True)
class AuthTokenTests(BaseTestCase, DRFTestCase):

    fixtures = ['test_projects_fixture_1.json']

    me_fields = list(
        Counter(FullUserSerializer.Meta.fields) - 
        Counter(['self'])
    )

    @classmethod
    def to_snake_case(cls, name):

        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

    @classmethod
    def remove_domain(cls, url):
        return re.sub(r'http://[a-zA-Z0-9\.]+', '', url)

    def check_activity_response(self, activity, user):
        '''
        A helper method that checks whether the activity data returned for the
        user 'user' is valid.
        '''

        # User URL
        self.assertIn('user', activity)
        self.assertEqual(
            self.remove_domain(activity['user']),
            reverse('api:user-detail', kwargs={'pk': user.id})
        )

        # Reviews
        self.assertIn('reviews', activity)
        user_reviews = Review.objects.filter(owner=user)
        self.assertEqual(len(activity['reviews']), user_reviews.count())
        self.assertSetEqual(set([r['id'] for r in activity['reviews']]), set([r.id for r in user_reviews]))
        for r in activity['reviews']:
            review_resp = self.client.get(r['self'])
            self.assertEqual(review_resp.status_code, 200)
            self.assertEqual(review_resp.data['text'], r['text'])

        #NOTE: for projects, lessons and classrooms - the id in activity is not the state id but the object referenced id itself.

        # Projects
        self.assertIn('projects', activity)
        user_projects = user.projects.all()
        self.assertEqual(len(activity['projects']), user_projects.count())
        self.assertSetEqual(set([p['id'] for p in activity['projects']]), set([p.project.id for p in user_projects]))
        for p in activity['projects']:
            project_resp = self.client.get(p['self'])
            self.assertEqual(project_resp.status_code, 200)
            self.assertEqual(project_resp.data['title'], p['title'])

            # Lessons
            self.assertIn('lessonStates', p)
            user_project_lessons = LessonState.objects.filter(project_state__user=user, project_state__project_id=p['id'])
            self.assertEqual(len(p['lessonStates']), user_project_lessons.count())
            self.assertSetEqual(set([l['id'] for l in p['lessonStates']]), set([l.lesson.id for l in user_project_lessons]))
            for l in p['lessonStates']:
                lesson_resp = self.client.get(l['self'])
                self.assertEqual(lesson_resp.status_code, 200)
                self.assertEqual(lesson_resp.data['title'], l['title'])

        # Classrooms
        self.assertIn('classrooms', activity)
        user_classrooms = user.classrooms_states.all()
        self.assertEqual(len(activity['classrooms']), user_classrooms.count())
        self.assertSetEqual(set([c['id'] for c in activity['classrooms']]), set([c.classroom.id for c in user_classrooms]))
        for l in activity['classrooms']:
            classroom_resp = self.client.get(l['self'])
            self.assertEqual(classroom_resp.status_code, 200)
            self.assertEqual(classroom_resp.data['title'], l['title'])
    
    def test_no_session_id(self):
        resp = self.client.post(reverse('api:get-auth-token'), {
            'secure_session_id': 1,
        })

        self.assertEqual(resp.status_code, 400)

    def test_no_secure_session_id(self):
        resp = self.client.post(reverse('api:get-auth-token'), {
            'session_id': 1,
        })

        self.assertEqual(resp.status_code, 400)

    @httpretty.activate
    def test_obtaining_token_with_session(self):

        session_id = '281500AC-08A4-477E-9705-2CC024D80869'
        secure_session_id = '21EFBFE7B31CC2E152EE7CB18A0B54D6'

        member_data = {
            'member_id': '281500AC-08A4-477E-9705-2CC024D80869',
            'email': 'o@o.com',
            'name': 'Ofir Ovadia',
            'short_name': 'Ofir',
            'avatar': 'http://placekitten.com/300/300/',
            'age': 28,
            'oxygen_id': 'zhNHUV9CJHL2Ryaw',
            'parent_email': '',
        }
        MockSparkDriveApi.mock_spark_drive_member(member_data, with_session={'session_id': session_id})

        resp = self.client.post(reverse('api:get-auth-token'), {
            'sessionId': session_id,
            'secureSessionId': secure_session_id
        })

        self.assertEqual(resp.status_code, 200)
        self.assertIn('token', resp.data)
        self.assertRegexpMatches(resp.data['token'], r'^[0-9a-fA-F]{40}$')

    @httpretty.activate
    def test_obtaining_token_child_user(self):

        session_id = '281500AC-08A4-477E-9705-2CC024D80869'
        secure_session_id = '21EFBFE7B31CC2E152EE7CB18A0B54D6'

        member_data = {
            'member_id': '281500AC-08A4-477E-9705-2CC024D80869',
            'email': 'o@o.com',
            'name': 'Ofir Ovadia',
            'first_name': 'Ofir',
            'age': 10,
            'oxygen_id': 'u98345934u590j1f',
            'avatar': 'http://placekitten.com/300/300/',
            'parent_email': 'parent@p.com.com',
        }
        MockSparkDriveApi.mock_spark_drive_member(member_data)

        resp = self.client.post(reverse('api:get-auth-token'), {
            'sessionId': session_id,
            'secureSessionId': secure_session_id
        })

        self.assertEqual(resp.status_code, 200)
        self.assertIn('token', resp.data)
        self.assertRegexpMatches(resp.data['token'], r'^[0-9a-fA-F]{40}$')

        db_user = get_user_model().objects.get(member_id=member_data['member_id'])
        self.assertTrue(db_user.is_child)

    @httpretty.activate
    def test_obtaining_token_with_session_no_age(self):
        '''Check that a user with no age, registers as an adult'''

        session_id = '281500AC-08A4-477E-9705-2CC024D80869'
        secure_session_id = '21EFBFE7B31CC2E152EE7CB18A0B54D6'

        member_data = {
            'member_id': '281500AC-08A4-477E-9705-2CC024D80869',
            'email': 'o@o.com',
            'name': 'Ofir Ovadia',
            'short_name': 'Ofir',
            'avatar': 'http://placekitten.com/300/300/',
            'oxygen_id': 'zhNHUV9CJHL2Ryaw',
        }
        MockSparkDriveApi.mock_spark_drive_member(member_data, omit_fields=['AGE', 'age'])

        resp = self.client.post(reverse('api:get-auth-token'), {
            'sessionId': session_id,
            'secureSessionId': secure_session_id
        })

        self.assertEqual(resp.status_code, 200)
        self.assertIn('token', resp.data)
        self.assertRegexpMatches(resp.data['token'], r'^[0-9a-fA-F]{40}$')

        db_user = get_user_model().objects.get(member_id=member_data['member_id'])
        self.assertFalse(db_user.is_child)

    @httpretty.activate
    def test_obtaining_token_age_is_zero(self):
        '''Make sure that a user with age (0) is a child'''
        
        session_id = '281500AC-08A4-477E-9705-2CC024D80869'
        secure_session_id = '21EFBFE7B31CC2E152EE7CB18A0B54D6'

        member_data = {
            'member_id': '281500AC-08A4-477E-9705-2CC024D80869',
            'email': 'o@o.com',
            'name': 'Ofir Ovadia',
            'first_name': 'Ofir',
            'age': 0,
            'oxygen_id': 'u98345934u590j1f',
            'avatar': 'http://placekitten.com/300/300/',
            'parent_email': 'parent@p.com.com',
        }
        MockSparkDriveApi.mock_spark_drive_member(member_data)

        resp = self.client.post(reverse('api:get-auth-token'), {
            'sessionId': session_id,
            'secureSessionId': secure_session_id
        })

        self.assertEqual(resp.status_code, 200)
        self.assertIn('token', resp.data)
        self.assertRegexpMatches(resp.data['token'], r'^[0-9a-fA-F]{40}$')

        db_user = get_user_model().objects.get(member_id=member_data['member_id'])
        self.assertTrue(db_user.is_child) # Is a child

    @httpretty.activate
    def test_obtaining_token_age_is_minus_one(self):
        '''Make sure that a user with age (-1) is not a child'''
        
        session_id = '281500AC-08A4-477E-9705-2CC024D80869'
        secure_session_id = '21EFBFE7B31CC2E152EE7CB18A0B54D6'

        member_data = {
            'member_id': '281500AC-08A4-477E-9705-2CC024D80869',
            'email': 'o@o.com',
            'name': 'Ofir Ovadia',
            'first_name': 'Ofir',
            'age': -1,
            'oxygen_id': 'u98345934u590j1f',
            'avatar': 'http://placekitten.com/300/300/',
        }
        MockSparkDriveApi.mock_spark_drive_member(member_data)

        resp = self.client.post(reverse('api:get-auth-token'), {
            'sessionId': session_id,
            'secureSessionId': secure_session_id
        })

        self.assertEqual(resp.status_code, 200)
        self.assertIn('token', resp.data)
        self.assertRegexpMatches(resp.data['token'], r'^[0-9a-fA-F]{40}$')

        db_user = get_user_model().objects.get(member_id=member_data['member_id'])
        self.assertFalse(db_user.is_child) # Not a child

    @httpretty.activate
    def test_incorrect_session_id(self):
        session_id = '281500AC-08A4-477E-9705-2CC024D80869'
        secure_session_id = '21EFBFE7B31CC2E152EE7CB18A0B54D6'

        member_data = {
            'member_id': '281500AC-08A4-477E-9705-2CC024D80869',
            'email': 'o@o.com',
            'name': 'Ofir Ovadia',
            'short_name': 'Ofir',
            'avatar': 'http://placekitten.com/300/300/',
            'age': 28,
            'oxygen_id': 'zhNHUV9CJHL2Ryaw',
        }
        MockSparkDriveApi.mock_spark_drive_member(member_data, with_session={'session_id': session_id})

        resp = self.client.post(reverse('api:get-auth-token'), {
            'sessionId': session_id + '_INVALID',
            'secureSessionId': secure_session_id
        })

        self.assertEqual(resp.status_code, 400)
        self.assertIn('non_field_errors', resp.data)

    @httpretty.activate
    def test_incorrect_secure_session_id(self):
        # NOTE: authentication via SparkDrive depends only session id, therefore incorrect secure session id will not
        #       fail authentication.

        session_id = '281500AC-08A4-477E-9705-2CC024D80869'
        secure_session_id = '21EFBFE7B31CC2E152EE7CB18A0B54D6'

        member_data = {
            'member_id': '281500AC-08A4-477E-9705-2CC024D80869',
            'email': 'o@o.com',
            'name': 'Ofir Ovadia',
            'short_name': 'Ofir',
            'avatar': 'http://placekitten.com/300/300/',
            'age': 28,
            'oxygen_id': 'zhNHUV9CJHL2Ryaw',
        }
        MockSparkDriveApi.mock_spark_drive_member(member_data, with_session={'session_id': session_id})

        resp = self.client.post(reverse('api:get-auth-token'), {
            'sessionId': session_id,
            'secureSessionId': secure_session_id + '_INVALID'
        })

        self.assertEqual(resp.status_code, 200)
        self.assertIn('token', resp.data)
        self.assertRegexpMatches(resp.data['token'], r'^[0-9a-fA-F]{40}$')

    @httpretty.activate
    def test_obtain_token_of_existing_user(self):

        session_id = '281500AC-08A4-477E-9705-2CC024D80869'
        secure_session_id = '21EFBFE7B31CC2E152EE7CB18A0B54D6'

        me = IgniteUser.objects.all()[0]
        token, _ = Token.objects.get_or_create(user=me)

        member_data = {
            'member_id': me.member_id,
            'email': me.email,
            'name': me.name,
            'short_name': me.short_name,
            'avatar': me.avatar,
            'age': 5 if me.is_child else 30,
            'oxygen_id': me.oxygen_id,
            'parent_email': me.parent_email,
        }
        MockSparkDriveApi.mock_spark_drive_member(member_data, with_session={'session_id': session_id})

        old_me_updated = me.updated

        resp = self.client.post(reverse('api:get-auth-token'), {
            'sessionId': session_id,
            'secureSessionId': secure_session_id
        })

        self.assertEqual(resp.status_code, 200)
        self.assertIn('token', resp.data)
        self.assertEqual(resp.data['token'], token.key)

        #check that updated time is not changed by log in:
        me = get_user_model().objects.get(pk=me.pk)
        self.assertEqual(me.updated, old_me_updated)

    @httpretty.activate
    def test_obtain_token_of_existing_user_with_changed_data(self):

        session_id = '281500AC-08A4-477E-9705-2CC024D80869'
        secure_session_id = '21EFBFE7B31CC2E152EE7CB18A0B54D6'

        me = IgniteUser.objects.all()[0]
        token, _ = Token.objects.get_or_create(user=me)

        member_data = {
            'member_id': me.member_id,
            'email': me.email,
            'name': me.name,
            'short_name': me.short_name + ' CHANGED!',
            'avatar': me.avatar,
            'age': 5 if me.is_child else 30,
            'oxygen_id': me.oxygen_id,
            'parent_email': me.parent_email,
        }
        MockSparkDriveApi.mock_spark_drive_member(member_data, with_session={'session_id': session_id})

        old_me_updated = me.updated

        resp = self.client.post(reverse('api:get-auth-token'), {
            'sessionId': session_id,
            'secureSessionId': secure_session_id
        })

        self.assertEqual(resp.status_code, 200)
        self.assertIn('token', resp.data)
        self.assertEqual(resp.data['token'], token.key)

        #check that updated time is not changed by log in:
        me = get_user_model().objects.get(pk=me.pk)
        self.assertGreater(me.updated, old_me_updated)

    @unittest.skip('Not implemented')
    def test_obtain_token_of_new_user(self):
        pass

    @unittest.skip('Not implemented')
    def test_obtaining_token_with_spark_token(self):
        pass

    def test_no_token_in_login_handler(self):

        mock_redirect = settings.IGNITE_FRONT_END_BASE_URL + 'fake/path/'
        resp = self.client.get(
            reverse('api:spark-login-handler', kwargs={'redirect': mock_redirect}),
            data={},
        )

        self.assertEqual(resp.status_code, 302)
        self.assertIn('loginError', resp.url)
        

    @override_settings(DEBUG=False)
    @override_settings(IGNITE_FRONT_END_BASE_URL='https://www.example.com/')
    def test_incorrect_redirect_path_on_prod(self):
        '''redirect argument that doesn't match the FE home URL should fail'''
        api = ObtainApiAuthToken()
        self.assertRaises(
            serializers.ValidationError,
            api.get,
            None, 
            'https://www.example2.com/path/to/resource/'
        )

    @override_settings(DEBUG=False)
    @override_settings(IGNITE_FRONT_END_BASE_URL='https://www.example.com/')
    def test_invalid_redirect_protocol_on_prod(self):
        '''redirect argument that doesn't match the FE home URL should fail'''
        api = ObtainApiAuthToken()
        self.assertRaises(
            serializers.ValidationError,
            api.get,
            None, 
            'ftp://www.example.com/path/to/resource/'
        )

    @override_settings(DEBUG=False)
    @override_settings(IGNITE_FRONT_END_BASE_URL='https://www.example.com/')
    def test_correct_redirect_path_on_prod(self):
        '''redirect argument that doesn't match the FE home URL should fail'''

        raised_exp = None
        try:
            api = ObtainApiAuthToken()
            api.get(None, 'http://www.example.com/path/to/resource/')
        except Exception, e:
            raised_exp = e

        self.assertIsNot(type(raised_exp), serializers.ValidationError)

    @override_settings(DEBUG=False)
    @override_settings(IGNITE_FRONT_END_BASE_URL='http://www.example.com/')
    def test_accept_any_protocol_in_redirect_path(self):
        '''redirect argument that doesn't match the FE home URL should fail'''

        raised_exp = None
        try:
            api = ObtainApiAuthToken()
            api.get(None, 'https://www.example.com/path/to/resource/')
        except Exception, e:
            raised_exp = e

        self.assertIsNot(type(raised_exp), serializers.ValidationError)

        raised_exp = None
        try:
            api = ObtainApiAuthToken()
            api.get(None, 'http://www.example.com/path/to/resource/')
        except Exception, e:
            raised_exp = e

        self.assertIsNot(type(raised_exp), serializers.ValidationError)

    @override_settings(DEBUG=True)
    @override_settings(IGNITE_FRONT_END_BASE_URL='http://www.example.com/')
    def test_on_dev_no_redirect_path_validation(self):
        '''redirect argument that doesn't match the FE home URL should fail'''

        raised_exp = None
        try:
            api = ObtainApiAuthToken()
            api.get(None, 'stamftp://ljsdhfkjhsafkhskfhs.org/path/to/resource/')
        except Exception, e:
            raised_exp = e

        self.assertIsNot(type(raised_exp), serializers.ValidationError)

    @httpretty.activate
    def test_login_handler_redirect_of_existing_user_already_logged_in_past(self):
        '''Checks redirect for an existing user that was already logged in the past.'''
        #get user and token:
        user = get_user_model().objects.first()
        user_token, _ = Token.objects.get_or_create(user=user)

        #set user last_login to be some date in the past (mocking already logged in the past):
        user.last_login = user.added
        user.save()

        #mock this URL only to make it past (data returned is not used in this test):
        session_id = 'D81500AC-08A4-477E-9705-DCC0D4D80869'
        secure_session_id = 'W1EFBFE7B31CCWE152EE7CB18A0B54D6'
        member_data = {
            'member_id': user.member_id,
            'email': user.email,
            'name': user.name,
            'first_name': user.short_name,
            'age': 5 if user.is_child else 28,
            'oxygen_id': user.oxygen_id,
            'avatar': user.avatar,
            'parent_email': user.parent_email,
        }
        MockSparkDriveApi.mock_spark_drive_token(session_id, secure_session_id)
        MockSparkDriveApi.mock_spark_drive_member(member_data)

        mock_oxygen = MockOxygen()
        mock_oxygen.mock_oxygen_operations(['get_child_status', 'get_child_moderators_all', 'get_moderator_children_all'])

        mock_redirect = settings.IGNITE_FRONT_END_BASE_URL + 'fake/path/'
        resp = self.client.get(
            reverse('api:spark-login-handler', kwargs={'redirect': mock_redirect}),
            data={'tokenkey': 'mytokenkey'},
        )

        self.assertRedirects(
            resp,
            mock_redirect + '?' + urllib.urlencode({
                    'sessionId': session_id,
                    'secureSessionId': secure_session_id,
                    'apiToken': user_token.key,
                }),
            fetch_redirect_response=False
        )

        user_after = get_user_model().objects.get(pk=user.pk)
        self.assertGreater(user_after.last_login, user.last_login)

    @httpretty.activate
    def test_login_handler_redirect_of_existing_user_never_logged_in_past(self):
        '''Checks redirect for an existing user that was already logged in the past.'''
        #get user and token:
        user = get_user_model().objects.first()
        user_token, _ = Token.objects.get_or_create(user=user)

        #set user last_login to be None (mocking never logged in the past):
        user.last_login = None
        user.save()

        #mock this URL only to make it past (data returned is not used in this test):
        session_id = 'D81500AC-08A4-477E-9705-DCC0D4D80869'
        secure_session_id = 'W1EFBFE7B31CCWE152EE7CB18A0B54D6'
        member_data = {
            'member_id': user.member_id,
            'email': user.email,
            'name': user.name,
            'first_name': user.short_name,
            'age': 5 if user.is_child else 28,
            'oxygen_id': user.oxygen_id,
            'avatar': user.avatar,
            'parent_email': '',
        }
        MockSparkDriveApi.mock_spark_drive_token(session_id, secure_session_id)
        MockSparkDriveApi.mock_spark_drive_member(member_data)

        mock_oxygen = MockOxygen()
        mock_oxygen.mock_oxygen_operations(['get_child_status', 'get_child_moderators_all', 'get_moderator_children_all'])

        mock_redirect = settings.IGNITE_FRONT_END_BASE_URL + 'fake/path/'
        resp = self.client.get(
            reverse('api:spark-login-handler', kwargs={'redirect': mock_redirect}),
            data={'tokenkey': 'mytokenkey'},
        )

        self.assertRedirects(
            resp,
            mock_redirect + '?' + urllib.urlencode({
                    'sessionId': session_id,
                    'secureSessionId': secure_session_id,
                    'apiToken': user_token.key,
                    'isFirstLogin': 'true',
                }),
            fetch_redirect_response=False
        )

        user_after = get_user_model().objects.get(pk=user.pk)
        self.assertIsNotNone(user_after.last_login)

    @httpretty.activate
    def test_login_handler_redirect_of_new_user(self):
        '''Checks redirect for an existing user that was already logged in the past.'''
        #mock this URL only to make it past (data returned is not used in this test):
        session_id = 'D81500AC-08A4-477E-9705-DCC0D4D80869'
        secure_session_id = 'W1EFBFE7B31CCWE152EE7CB18A0B54D6'
        new_user_member_id = 'new12345'
        member_data = {
            'member_id': new_user_member_id,
            'email': 'new@user.com',
            'name': 'New User 1',
            'first_name': 'User',
            'age': 5,
            'oxygen_id': 'new_ox12345',
            'avatar': 'http://new_user.com/avatar.jpg',
            'parent_email': 'parent@p.com.com',
        }
        MockSparkDriveApi.mock_spark_drive_token(session_id, secure_session_id)
        MockSparkDriveApi.mock_spark_drive_member(member_data)

        mock_oxygen = MockOxygen()
        mock_oxygen.mock_oxygen_operations(['get_child_status', 'get_child_moderators_all', 'get_moderator_children_all'])

        mock_redirect = settings.IGNITE_FRONT_END_BASE_URL + 'fake/path/'
        resp = self.client.get(
            reverse('api:spark-login-handler', kwargs={'redirect': mock_redirect}),
            data={'tokenkey': 'mytokenkey'},
        )

        #get the new user and token:
        user = get_user_model().objects.get(member_id=new_user_member_id)
        user_token = Token.objects.get(user=user)

        self.assertRedirects(
            resp,
            mock_redirect + '?' + urllib.urlencode({
                    'sessionId': session_id,
                    'secureSessionId': secure_session_id,
                    'apiToken': user_token.key,
                    'isFirstLogin': 'true',
                }),
            fetch_redirect_response=False
        )

        self.assertIsNotNone(user.last_login)


    def test_get_me(self):

        me = IgniteUser.objects.all()[0]
        self.client.force_authenticate(me)

        resp = self.client.get(reverse('api:me'))
        self.assertEqual(resp.status_code, 200)

        for field_name in self.me_fields:

            if field_name == 'joined':
                self.assertEqual(parse_datetime(resp.data[field_name]), me.added)
            else:
                db_value = getattr(
                    me,
                    (
                        FullUserSerializer().get_fields()[field_name].source or 
                        self.to_snake_case(field_name)
                    ),
                )
                if hasattr(db_value, 'all'):
                    db_value = list(db_value.all())

                self.assertEqual(resp.data[field_name], db_value)

    def test_cant_get_me_if_not_authenticated(self):

        self.client.force_authenticate(None)

        resp = self.client.get(reverse('api:me'))

        self.assertEqual(resp.status_code, 401)

    def test_cant_perform_non_safe_action_on_me(self):
        actions = ['post', 'delete']

        self.client.force_authenticate(IgniteUser.objects.all()[0])

        for action in actions:
            resp = getattr(self.client, action)(reverse('api:me'), {})

            self.assertEqual(resp.status_code, 405)

    @httpretty.activate
    def test_profile_edit_user_data(self):
        '''
        Tests that user can edit his own profile user data.
        '''

        user = IgniteUser.objects.all()[0]
        self.client.force_authenticate(user)

        data = {
            'sessionId': '281500AC-08A4-477E-9705-2CC024D80869',
            'secureSessionId': '21EFBFE7B31CC2E152EE7CB18A0B54D6',

            'name': 'Hokus Pokus',
            'avatar': 'http://host.com/cats/kitty.jpg',
            'description': 'My Ignite BIO',
        }
        data_changed = {
            'name': data['name'],
            'profile': {
                'avatar_path': 'https://storage.host/profiles/avatar-13923912.jpg',
            },
            'description': 'SparkDrive user BIO',
        }

        #mock spark drive api:
        mock_upload_server = 'mock.upload.server'
        httpretty.register_uri(
            httpretty.GET, settings.SPARK_DRIVE_API+'/api/v2/server/upload',
            body=json.dumps({'server':mock_upload_server}),
        )
        httpretty.register_uri(
            httpretty.POST, 'https://'+mock_upload_server+'/api/v2/files/upload',
            body=json.dumps({'files': [{'file_id': '123456'}]}),
        )
        httpretty.register_uri(
            httpretty.PUT, settings.SPARK_DRIVE_API+'/api/v2/members/%s'%(user.member_id,),
            body=json.dumps({}),
        )
        httpretty.register_uri(
            httpretty.GET, settings.SPARK_DRIVE_API+'/api/v2/members/%s'%(user.member_id,),
            body=json.dumps({'member': data_changed}),
        )

        old_user_updated = user.updated

        resp = self.client.put(reverse('api:me'), data=data)
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(resp.data['name'], data_changed['name'])
        self.assertEqual(resp.data['avatar'], data_changed['profile']['avatar_path'])
        self.assertEqual(resp.data['description'], data['description'])  #shoould not be synchronized with SparkDrive

        #check that updated time was changed:
        user = get_user_model().objects.get(pk=user.pk)
        self.assertGreater(user.updated, old_user_updated)

    @httpretty.activate
    def test_profile_edit_user_data_without_change_of_avatar_and_name(self):
        '''
        Tests that if user tries to edit his profile with the same current data, then SparkDrive will not be called.
        '''

        user = IgniteUser.objects.all()[0]
        self.client.force_authenticate(user)

        data = {
            'sessionId': '281500AC-08A4-477E-9705-2CC024D80869',
            'secureSessionId': '21EFBFE7B31CC2E152EE7CB18A0B54D6',

            'name': 'Hokus Pokus',
            'avatar': 'http://host.com/cats/kitty.jpg',
            'description': 'My Ignite BIO',
        }
        data_changed = {
            'name': data['name'] + '-SPARK',
            'profile': {
                'avatar_path': data['avatar'] + '-SPARK',
            },
            'description': data['description'] + '-SPARK',
        }

        #mock spark drive api:
        mock_upload_server = 'mock.upload.server'
        httpretty.register_uri(
            httpretty.GET, settings.SPARK_DRIVE_API+'/api/v2/server/upload',
            body=json.dumps({'server':mock_upload_server}),
        )
        httpretty.register_uri(
            httpretty.POST, 'https://'+mock_upload_server+'/api/v2/files/upload',
            body=json.dumps({'files': [{'file_id': '123456'}]}),
        )
        httpretty.register_uri(
            httpretty.PUT, settings.SPARK_DRIVE_API+'/api/v2/members/%s'%(user.member_id,),
            body=json.dumps({}),
        )
        httpretty.register_uri(
            httpretty.GET, settings.SPARK_DRIVE_API+'/api/v2/members/%s'%(user.member_id,),
            body=json.dumps({'member': data_changed}),
        )

        # already apply the new user SparkDrive data (name and avatar) to the user object:
        user.name = data['name']
        user.avatar = data['avatar']
        user.save()

        old_user_updated = user.updated

        resp = self.client.put(reverse('api:me'), data=data)
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(resp.data['name'], data['name'])
        self.assertEqual(resp.data['avatar'], data['avatar'])
        self.assertEqual(resp.data['description'], data['description'])  #shoould not be synchronized with SparkDrive

        #check that updated time was changed:
        user = get_user_model().objects.get(pk=user.pk)
        self.assertGreater(user.updated, old_user_updated)

    def test_profile_child_edit_user_type(self):
        '''
        Tests that child user can not change his user type to parent or teacher.
        '''

        user_adult = IgniteUser.objects.filter(is_child=False).all()[0]
        user_child = IgniteUser.objects.filter(is_child=True).all()[0]

        for user in [user_adult, user_child]:
            for user_type, _ in IgniteUser.USER_TYPES:
                self.client.force_authenticate(user)

                resp = self.client.put(
                    reverse('api:me'),
                    data={
                        'userType': user_type,
                    }
                )
                if not user.is_child or user_type not in [IgniteUser.TEACHER, IgniteUser.PARENT]:
                    self.assertEqual(resp.status_code, 200)
                    self.assertEqual(resp.data['userType'], user_type)
                    u = IgniteUser.objects.get(pk=user.pk)
                    self.assertEqual(u.user_type, user_type)
                else:
                    self.assertEqual(resp.status_code, 400)
                    self.assertIn('userType', resp.data)

    @httpretty.activate
    def test_profile_edit_user_data_sparkdrive_error(self):
        '''
        Tests that SparkDrive error is well handled.
        '''

        user = IgniteUser.objects.all()[0]
        self.client.force_authenticate(user)

        data = {
            'sessionId': '281500AC-08A4-477E-9705-2CC024D80869',
            'secureSessionId': '21EFBFE7B31CC2E152EE7CB18A0B54D6',

            'name': 'Hokus Pokus',
        }
        data_changed = {
            'name': data['name'],
            'profile': {
                'avatar_path': 'https://storage.host/profiles/avatar-13923912.jpg',
            },
        }

        #mock spark drive api:
        mock_upload_server = 'mock.upload.server'
        httpretty.register_uri(
            httpretty.PUT, settings.SPARK_DRIVE_API+'/api/v2/members/%s'%(user.member_id,),
            body=json.dumps({
                'code': 0,  #unknown error
            }),
            status=404,
        )
        resp = self.client.put(reverse('api:me'), data=data)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('non_field_errors', resp.data)

    @httpretty.activate
    def test_profile_edit_user_data_error_name_already_taken(self):
        '''
        Tests that SparkDrive error of name already exists is well handled.
        '''

        user = IgniteUser.objects.all()[0]
        self.client.force_authenticate(user)

        data = {
            'sessionId': '281500AC-08A4-477E-9705-2CC024D80869',
            'secureSessionId': '21EFBFE7B31CC2E152EE7CB18A0B54D6',

            'name': 'Hokus Pokus',
        }
        data_changed = {
            'name': data['name'],
            'profile': {
                'avatar_path': 'https://storage.host/profiles/avatar-13923912.jpg',
            },
        }

        #mock spark drive api:
        mock_upload_server = 'mock.upload.server'
        httpretty.register_uri(
            httpretty.PUT, settings.SPARK_DRIVE_API+'/api/v2/members/%s'%(user.member_id,),
            body=json.dumps({
                'code': 4001,  # SparkDrive error code for: name is already taken
            }),
            status=404,
        )
        resp = self.client.put(reverse('api:me'), data=data)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('name', resp.data)

    @httpretty.activate
    def test_profile_edit_user_data_sparkdrive_fields_require_session_and_secure(self):
        '''
        Tests that SparkDrive fields (name, avatar) require sessionId and secureSessionId.
        '''

        user = IgniteUser.objects.all()[0]
        self.client.force_authenticate(user)

        datas = [
            {'name': 'Hokus Pokus'},
            {'avatar': 'http://host.com/cats/kitty.jpg'},
        ]

        for data in datas:
            resp = self.client.put(reverse('api:me'), data=data)

            self.assertEqual(resp.status_code, 400)
            self.assertIn('sessionId', resp.data)
            self.assertIn('secureSessionId', resp.data)

    @httpretty.activate
    def test_profile_edit_user_data_non_sparkdrive_fields_not_require_session_and_secure(self):
        '''
        Tests that non SparkDrive fields (description) do not require sessionId and secureSessionId.
        '''

        user = IgniteUser.objects.all()[0]
        self.client.force_authenticate(user)

        data = {
            'description': 'My Ignite BiO',
            'showAuthoringTooltips': False,
        }

        old_user_updated = user.updated

        resp = self.client.put(reverse('api:me'), data=data)
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(resp.data['description'], data['description'])  #shoould not be synchronized with SparkDrive
        self.assertEqual(resp.data['showAuthoringTooltips'], data['showAuthoringTooltips'])  #no reflection in SparkDrive

        #check that updated time was changed:
        user = get_user_model().objects.get(pk=user.pk)
        self.assertGreater(user.updated, old_user_updated)


    # COPPA
    # #####


    @httpretty.activate
    @patch_redis
    def test_prepare_paypal_link(self):
        '''Regular POST to get a Paypal link'''

        token = 'mock1paypal2token3response456'
        authorization_code = '786359231740'
        session_id = 'haioeasdjkfhewr'
        secure_session_id = 'ja983y92h3823hrr3-1231'
        user = get_user_model().objects.filter(
            is_verified_adult=False, is_child=False
        ).first()
        self.client.force_authenticate(user)

        httpretty.register_uri(
            httpretty.GET,
            settings.PAYPAL_NVP_BASE_URL,
            body='ACK=Success&TOKEN=%s' % token
        )

        r = get_redis_connection('default')
        all_keys = r.keys()

        resp = self.client.post(
            reverse('api:verify-adult'),
            {
                'sessionId': session_id,
                'secureSessionId': secure_session_id,
                'authorizationCode': authorization_code,
            },
        )

        self.assertEqual(resp.status_code, 200)
        self.assertIn('redirect', resp.data)
        self.assertIn(settings.PAYPAL_BASE_URL, resp.data['redirect'])
        self.assertIn('cmd=_express-checkout', resp.data['redirect'])

        new_keys = [k for k in r.keys() if k not in all_keys]

        # Redis has user_object
        self.assertEqual(len(new_keys), 1)
        self.assertIn(RedisAuthentication.REDIS_AUTH_PREFIX, new_keys[0])
        user_obj = r.hgetall(new_keys[0])
        self.assertEqual(str(user_obj['user_id']), str(user.id))
        self.assertEqual(user_obj['authorization_code'], authorization_code)
        self.assertEqual(user_obj['session_id'], session_id)
        self.assertEqual(user_obj['secure_session_id'], secure_session_id)

        # Redis Token equals URL Token
        self.assertEqual(user_obj['token'], token)

        # Check request made to Paypal.
        self.assertDictContainsSubset({
            'METHOD': ['SetExpressCheckout'],
            'PAYMENTREQUEST_0_PAYMENTACTION': ['SALE'],
            'PAYMENTREQUEST_0_AMT': ['0.5'],
            'PAYMENTREQUEST_0_CURRENCYCODE': ['USD'],
            'USER': [settings.PAYPAL_USERNAME],
            'PWD': [settings.PAYPAL_PASSWORD],
            'SIGNATURE': [settings.PAYPAL_SIGNATURE],
            'VERSION': [str(settings.PAYPAL_VERSION)],
            'cancelUrl': [settings.IGNITE_FRONT_END_MODERATION_URL],
        }, httpretty.last_request().querystring)
        self.assertIn(
            reverse('api:verify-adult-2nd-stage',kwargs={
                'hash': new_keys[0][len(RedisAuthentication.REDIS_AUTH_PREFIX):]
            }).replace('%3D', '='),
            httpretty.last_request().querystring['returnUrl'][0]
        )

        # Check Redis key expires in 1 hour
        self.assertLessEqual(r.ttl(new_keys[0]), 60*60)

    def test_prepare_paypal_link_invlalid_input(self):
        '''Regular POST to get a Paypal link with invalid input'''

        post_input = {
            'sessionId': '786359231740',
            'secureSessionId': 'haioeasdjkfhewr',
            'authorizationCode': 'ja983y92h3823hrr3-1231',
        }
        user = get_user_model().objects.filter(
            is_verified_adult=False, is_child=False
        ).first()
        self.client.force_authenticate(user)

        for key in post_input.keys():
            resp = self.client.post(
                reverse('api:verify-adult'),
                {k:v for k,v in post_input.items() if k != key},
            )

            self.assertEqual(resp.status_code, 400)
            self.assertIn(key, resp.data)

    @httpretty.activate
    @patch_redis
    def test_prepare_paypal_link_set_express_checkout_fails(self):
        '''Regular POST to get a Paypal link. Paypal returns an error.'''

        authorization_code = '786359231740'
        session_id = 'haioeasdjkfhewr'
        secure_session_id = 'ja983y92h3823hrr3-1231'
        user = get_user_model().objects.filter(
            is_verified_adult=False, is_child=False
        ).first()
        self.client.force_authenticate(user)

        httpretty.register_uri(
            httpretty.GET,
            settings.PAYPAL_NVP_BASE_URL,
            body='ACK=Failure',
            status=400,
        )

        r = get_redis_connection('default')
        all_keys = r.keys()

        self.assertRaises(Exception, self.client.post,
            reverse('api:verify-adult'),
            {
                'sessionId': session_id,
                'secureSessionId': secure_session_id,
                'authorizationCode': authorization_code,
            },
        )

    def prepare_child_authorization(self, user=None, child_user=None):
        '''
        SetUp all that is needed for checking the child_authorize method.

        This is used both in the Paypal reply and when a verified adult POSTs
        directly to  authorize the child.
        '''

        authorization_code = '111111111111'

        token = 'mock1paypal2token3response456'
        url_hash = 'testtesttesttesttesttesttesttesttest'

        if not child_user:
            child_user = get_user_model().objects.filter(
                is_child=True, is_approved=False,
            ).first()

        if not user:
            user = get_user_model().objects.filter(
                is_verified_adult=False, is_child=False,
            ).first()

        #mock Oxygen operation for authorize and approve moderator child:
        mock_oxygen = MockOxygen()
        mock_oxygen.set_mock_user_as_instance(user)
        mock_oxygen.set_mock_user_as_instance(child_user)
        mock_oxygen.set_mock_authorization_link(authorization_code, user.oxygen_id, child_user.oxygen_id)
        mock_oxygen.mock_oxygen_operations(['authorize_and_approve_moderator_child'])

        return (mock_oxygen, authorization_code, user, child_user, token, url_hash)


    def prepare_paypal_reply(self, skip_paypal_registration=False):
        '''
        SetUp all that is needed for checking the Paypal redirect reply (GET)
        '''

        mock_oxygen, authorization_code, user, child_user, token, url_hash = self.prepare_child_authorization(None, None)

        session_id = '2222222222222'
        secure_session_id = '3333333333333'
        payer_id = 'lksadjflkasdjflsakjweioro039'

        def check_paypal_requests(request, uri, headers):

            params = request.querystring

            self.assertDictContainsSubset({
                'USER': [settings.PAYPAL_USERNAME],
                'PWD': [settings.PAYPAL_PASSWORD],
                'SIGNATURE': [settings.PAYPAL_SIGNATURE],
                'VERSION': [str(settings.PAYPAL_VERSION)],
            }, params)

            if params['METHOD'][0] == 'GetExpressCheckoutDetails':
                self.assertDictContainsSubset({
                    'TOKEN': [token],
                }, params)
            elif params['METHOD'][0] == 'DoExpressCheckoutPayment':
                self.assertDictContainsSubset({
                    'TOKEN': [token],
                    'PAYERID': [payer_id],
                    'PAYMENTREQUEST_0_AMT': ['0.5'],
                    'PAYMENTREQUEST_0_PAYMENTACTION': ['SALE'],
                    'PAYMENTREQUEST_0_CURRENCYCODE': ['USD'],
                }, params)

            return (200, headers, 'ACK=Success&TOKEN=%s&PAYERID=%s' % (token, payer_id))



        if not skip_paypal_registration:
            httpretty.register_uri(
                httpretty.GET,
                settings.PAYPAL_NVP_BASE_URL,
                body=check_paypal_requests
            )

        r = get_redis_connection('default')
        r.hmset(RedisAuthentication.REDIS_AUTH_PREFIX + url_hash, {
            'user_id': user.id,
            'authorization_code': authorization_code,
            'token': token,
            'session_id': session_id,
            'secure_session_id': secure_session_id,
        })
        r.expire(RedisAuthentication.REDIS_AUTH_PREFIX + url_hash, 60) # 1 Minute
        r.hdel(RedisAuthentication.REDIS_AUTH_PREFIX + url_hash, 'temp_child_id')

        return (mock_oxygen, authorization_code, user, child_user, token, url_hash)

    @httpretty.activate
    @patch_redis
    def test_paypal_reply(self):
        '''GET from Paypal, after the user has visited there.'''

        mock_oxygen, authorization_code, user, child_user, token, url_hash = self.prepare_paypal_reply()

        resp = self.client.get(
            reverse('api:verify-adult-2nd-stage', kwargs={'hash': url_hash}),
            {
                'token': token,
            },
        )

        # Request succeeded.
        self.assertRedirects(
            resp,
            (settings.IGNITE_FRONT_END_MODERATION_URL +
                '?verifiedAuthorizationCode=%s' % authorization_code
            ),
            fetch_redirect_response=False
        )
        self.assertNotIn('error', resp.url)

        # Check temp_child_id in Redis
        r = get_redis_connection('default')
        self.assertEqual(r.hget(RedisAuthentication.REDIS_AUTH_PREFIX + url_hash, 'temp_child_id'), str(child_user.id))

        # Check that user is adult.
        user_after = get_user_model().objects.get(id=user.id)
        self.assertTrue(user_after.is_verified_adult)

        # Check that child is verified.
        child_after = get_user_model().objects.get(id=child_user.id)
        self.assertTrue(child_after.is_approved)

        # Check that 'user' is the child's guardian.
        self.assertIn(
            user.id,
            list(child_after.guardians.all().values_list('id', flat=True)),
        )

    # @httpretty.activate
    @patch_redis
    def test_paypal_reply_token_doesnt_match(self):
        '''Token in reply message doesn't match the token in the Redis object'''

        mock_oxygen, authorization_code, user, child_user, token, url_hash = self.prepare_paypal_reply()

        resp = self.client.get(
            reverse('api:verify-adult-2nd-stage', kwargs={'hash': url_hash}),
            {
                'token': 'DIFFERENT-TOKEN',
            },
        )

        # Request returned error.
        self.assertEqual(resp.status_code, 302)
        self.assertIn(settings.IGNITE_FRONT_END_MODERATION_URL, resp.url)
        self.assertIn('error', resp.url)
        self.assertNotIn('verifiedAuthorizationCode', resp.url)
        self.assertNotIn('success', resp.url)

        # Check that user is not.
        user_after = get_user_model().objects.get(id=user.id)
        self.assertFalse(user_after.is_verified_adult)

        # Check that child is not verified.
        child_after = get_user_model().objects.get(id=child_user.id)
        self.assertFalse(child_after.is_approved)

        # Check that 'user' is not the child's guardian.
        self.assertEqual(child_after.guardians.all().count(), 0)

    @httpretty.activate
    @patch_redis
    def test_paypal_reply_redis_record_not_found(self):
        '''If Redis record does not exist, action fails, but user is redirected'''

        mock_oxygen, authorization_code, user, child_user, token, url_hash = self.prepare_paypal_reply()

        r = get_redis_connection('default')
        r.delete(RedisAuthentication.REDIS_AUTH_PREFIX + url_hash)

        resp = self.client.get(
            reverse('api:verify-adult-2nd-stage', kwargs={'hash': url_hash}),
            {
                'token': token,
            },
        )

        # Request returned error.
        self.assertEqual(resp.status_code, 302)
        self.assertIn(settings.IGNITE_FRONT_END_MODERATION_URL, resp.url)
        self.assertIn('error', resp.url)
        self.assertNotIn('verifiedAuthorizationCode', resp.url)
        self.assertNotIn('success', resp.url)

        # Check that user is not.
        user_after = get_user_model().objects.get(id=user.id)
        self.assertFalse(user_after.is_verified_adult)

        # Check that child is not verified.
        child_after = get_user_model().objects.get(id=child_user.id)
        self.assertFalse(child_after.is_approved)

        # Check that 'user' is not the child's guardian.
        self.assertEqual(child_after.guardians.all().count(), 0)

    @httpretty.activate
    @patch_redis
    def test_paypal_reply_get_express_checkout_details_fails(self):
        '''Paypal redirect reply (GET) fails on GetExpressCheckoutDetails'''

        mock_oxygen, authorization_code, user, child_user, token, url_hash = self.prepare_paypal_reply(
            skip_paypal_registration=True
        )
        payer_id = 'my-different-payer-id'

        def check_paypal_requests(request, uri, headers):

            params = request.querystring

            self.assertDictContainsSubset({
                'USER': [settings.PAYPAL_USERNAME],
                'PWD': [settings.PAYPAL_PASSWORD],
                'SIGNATURE': [settings.PAYPAL_SIGNATURE],
                'VERSION': [str(settings.PAYPAL_VERSION)],
            }, params)

            if params['METHOD'][0] == 'GetExpressCheckoutDetails':
                self.assertDictContainsSubset({
                    'TOKEN': [token],
                }, params)

                return (401, headers, 'ACK=Success&TOKEN=%s&PAYERID=%s' % (token, payer_id))
            elif params['METHOD'][0] == 'DoExpressCheckoutPayment':
                self.assertDictContainsSubset({
                    'TOKEN': [token],
                    'PAYERID': [payer_id],
                    'PAYMENTREQUEST_0_AMT': ['0.5'],
                    'PAYMENTREQUEST_0_PAYMENTACTION': ['SALE'],
                    'PAYMENTREQUEST_0_CURRENCYCODE': ['USD'],
                }, params)

                return (200, headers, 'ACK=Success&TOKEN=%s&PAYERID=%s' % (token, payer_id))

        httpretty.register_uri(
            httpretty.GET,
            settings.PAYPAL_NVP_BASE_URL,
            body=check_paypal_requests
        )

        resp = self.client.get(
            reverse('api:verify-adult-2nd-stage', kwargs={'hash': url_hash}),
            {
                'token': token,
            },
        )

        # Request returned error.
        self.assertEqual(resp.status_code, 302)
        self.assertIn(settings.IGNITE_FRONT_END_MODERATION_URL, resp.url)
        self.assertIn('error', resp.url)
        self.assertNotIn('verifiedAuthorizationCode', resp.url)
        self.assertNotIn('success', resp.url)

        # Check that user is not.
        user_after = get_user_model().objects.get(id=user.id)
        self.assertFalse(user_after.is_verified_adult)

        # Check that child is not verified.
        child_after = get_user_model().objects.get(id=child_user.id)
        self.assertFalse(child_after.is_approved)

        # Check that 'user' is not the child's guardian.
        self.assertEqual(child_after.guardians.all().count(), 0)

    @httpretty.activate
    @patch_redis
    def test_paypal_reply_do_express_checkout_fails(self):
        '''Paypal redirect reply (GET) fails on DoExpressCheckoutPayment'''

        mock_oxygen, authorization_code, user, child_user, token, url_hash = self.prepare_paypal_reply(
            skip_paypal_registration=True
        )
        payer_id = 'my-different-payer-id'

        def check_paypal_requests(request, uri, headers):

            params = request.querystring

            self.assertDictContainsSubset({
                'USER': [settings.PAYPAL_USERNAME],
                'PWD': [settings.PAYPAL_PASSWORD],
                'SIGNATURE': [settings.PAYPAL_SIGNATURE],
                'VERSION': [str(settings.PAYPAL_VERSION)],
            }, params)

            if params['METHOD'][0] == 'GetExpressCheckoutDetails':
                self.assertDictContainsSubset({
                    'TOKEN': [token],
                }, params)

                return (200, headers, 'ACK=Success&TOKEN=%s&PAYERID=%s' % (token, payer_id))

            elif params['METHOD'][0] == 'DoExpressCheckoutPayment':
                self.assertDictContainsSubset({
                    'TOKEN': [token],
                    'PAYERID': [payer_id],
                    'PAYMENTREQUEST_0_AMT': ['0.5'],
                    'PAYMENTREQUEST_0_PAYMENTACTION': ['SALE'],
                    'PAYMENTREQUEST_0_CURRENCYCODE': ['USD'],
                }, params)

                return (200, headers, 'ACK=Failure&TOKEN=%s&PAYERID=%s' % (token, payer_id))

        httpretty.register_uri(
            httpretty.GET,
            settings.PAYPAL_NVP_BASE_URL,
            body=check_paypal_requests
        )

        resp = self.client.get(
            reverse('api:verify-adult-2nd-stage', kwargs={'hash': url_hash}),
            {
                'token': token,
            },
        )

        # Request returned error.
        self.assertEqual(resp.status_code, 302)
        self.assertIn(settings.IGNITE_FRONT_END_MODERATION_URL, resp.url)
        self.assertIn('error', resp.url)
        self.assertNotIn('verifiedAuthorizationCode', resp.url)
        self.assertNotIn('success', resp.url)

        # Check that user is not.
        user_after = get_user_model().objects.get(id=user.id)
        self.assertFalse(user_after.is_verified_adult)

        # Check that child is not verified.
        child_after = get_user_model().objects.get(id=child_user.id)
        self.assertFalse(child_after.is_approved)

        # Check that 'user' is not the child's guardian.
        self.assertEqual(child_after.guardians.all().count(), 0)

    @httpretty.activate
    @patch_redis
    def test_paypal_reply_oxygen_auth_mod_returns_invalid_auth_code_child_not_in_redis(self):
        '''Paypal redirect reply (GET) fails on Oxygen's Auth Moderator. Cannot overcome issue cause child not in Redis'''

        #force authorize moderator child to fail:
        mock_oxygen, authorization_code, user, child_user, token, url_hash = self.prepare_paypal_reply()
        mock_oxygen.authorization_links = {}

        r = get_redis_connection('default')
        r.hdel(RedisAuthentication.REDIS_AUTH_PREFIX + url_hash, 'temp_child_id')

        resp = self.client.get(
            reverse('api:verify-adult-2nd-stage', kwargs={'hash': url_hash}),
            {
                'token': token,
            },
        )

        # Request returned error.
        self.assertEqual(resp.status_code, 302)
        self.assertIn(settings.IGNITE_FRONT_END_MODERATION_URL, resp.url)
        self.assertIn('error', resp.url)
        self.assertIn('success', resp.url)
        self.assertNotIn('verifiedAuthorizationCode', resp.url)

        # Check that user is adult.
        user_after = get_user_model().objects.get(id=user.id)
        self.assertTrue(user_after.is_verified_adult)

        # Check that child is not verified.
        child_after = get_user_model().objects.get(id=child_user.id)
        self.assertFalse(child_after.is_approved)

        # Check that 'user' is not the child's guardian.
        self.assertEqual(child_after.guardians.all().count(), 0)

    @httpretty.activate
    @patch_redis
    def test_paypal_reply_oxygen_auth_mod_returns_invalid_auth_code_child_in_redis_and_linked_to_guardian(self):
        '''Paypal redirect reply (GET) fails on Oxygen's Auth Moderator. Can overcome issue cause child is in Redis and linked to the guardian'''

        #force authorize moderator child to fail:
        mock_oxygen, authorization_code, user, child_user, token, url_hash = self.prepare_paypal_reply()
        mock_oxygen.authorization_links = {}

        #link child to guardian and put it in Redis:
        ChildGuardian(
            guardian=user,
            child=child_user
        ).save()
        mock_oxygen.set_mock_user_as_instance(user)
        r = get_redis_connection('default')
        r.hset(RedisAuthentication.REDIS_AUTH_PREFIX + url_hash, 'temp_child_id', str(child_user.id))

        resp = self.client.get(
            reverse('api:verify-adult-2nd-stage', kwargs={'hash': url_hash}),
            {
                'token': token,
            },
        )

        # Request succeeded.
        self.assertRedirects(
            resp,
            (settings.IGNITE_FRONT_END_MODERATION_URL +
                '?verifiedAuthorizationCode=%s' % authorization_code
            ),
            fetch_redirect_response=False
        )
        self.assertNotIn('error', resp.url)

        # Check temp_child_id in Redis
        r = get_redis_connection('default')
        self.assertEqual(r.hget(RedisAuthentication.REDIS_AUTH_PREFIX + url_hash, 'temp_child_id'), str(child_user.id))

        # Check that user is adult.
        user_after = get_user_model().objects.get(id=user.id)
        self.assertTrue(user_after.is_verified_adult)

        # Check that child is verified.
        child_after = get_user_model().objects.get(id=child_user.id)
        self.assertTrue(child_after.is_approved)

        # Check that 'user' is the child's guardian.
        self.assertIn(
            user.id,
            list(child_after.guardians.all().values_list('id', flat=True)),
        )

    @httpretty.activate
    @patch_redis
    def test_paypal_reply_oxygen_auth_mod_returns_invalid_auth_code_child_in_redis_but_not_linked_to_guardian(self):
        '''Paypal redirect reply (GET) fails on Oxygen's Auth Moderator. Fails cause child is not linked to guardian.'''

        #force authorize moderator child to fail:
        mock_oxygen, authorization_code, user, child_user, token, url_hash = self.prepare_paypal_reply()
        mock_oxygen.authorization_links = {}

        #add child to Redis, but not link child to guardian:
        r = get_redis_connection('default')
        r.hset(RedisAuthentication.REDIS_AUTH_PREFIX + url_hash, 'temp_child_id', str(child_user.id))

        resp = self.client.get(
            reverse('api:verify-adult-2nd-stage', kwargs={'hash': url_hash}),
            {
                'token': token,
            },
        )

        # Request returned error.
        self.assertEqual(resp.status_code, 302)
        self.assertIn(settings.IGNITE_FRONT_END_MODERATION_URL, resp.url)
        self.assertIn('error', resp.url)
        self.assertIn('success', resp.url)
        self.assertNotIn('verifiedAuthorizationCode', resp.url)

        # Check temp_child_id in Redis
        r = get_redis_connection('default')
        self.assertEqual(r.hget(RedisAuthentication.REDIS_AUTH_PREFIX + url_hash, 'temp_child_id'), str(child_user.id))

        # Check that user is adult.
        user_after = get_user_model().objects.get(id=user.id)
        self.assertTrue(user_after.is_verified_adult)

        # Check that child is not verified.
        child_after = get_user_model().objects.get(id=child_user.id)
        self.assertFalse(child_after.is_approved)

        # Check that 'user' is not the child's guardian.
        self.assertEqual(child_after.guardians.all().count(), 0)

    @httpretty.activate
    @patch_redis
    def test_paypal_reply_oxygen_auth_mod_when_auth_code_fails(self):
        '''Paypal redirect reply (GET) fails on Oxygen's Auth Moderator'''

        #force authorize moderator child to fail:
        mock_oxygen, authorization_code, user, child_user, token, url_hash = self.prepare_paypal_reply()
        mock_oxygen.authorization_links = {}

        r = get_redis_connection('default')
        r.hdel(RedisAuthentication.REDIS_AUTH_PREFIX + url_hash, 'temp_child_id')
        resp = self.client.get(
            reverse('api:verify-adult-2nd-stage', kwargs={'hash': url_hash}),
            {
                'token': token,
            },
        )

        # Request returned error.
        self.assertEqual(resp.status_code, 302)
        self.assertIn(settings.IGNITE_FRONT_END_MODERATION_URL, resp.url)
        self.assertIn('error', resp.url)
        self.assertIn('success', resp.url)
        self.assertNotIn('verifiedAuthorizationCode', resp.url)

        # Check that user is adult.
        user_after = get_user_model().objects.get(id=user.id)
        self.assertTrue(user_after.is_verified_adult)

        # Check that child is not verified.
        child_after = get_user_model().objects.get(id=child_user.id)
        self.assertFalse(child_after.is_approved)

        # Check that 'user' is not the child's guardian.
        self.assertEqual(child_after.guardians.all().count(), 0)

    @httpretty.activate
    @patch_redis
    def test_paypal_reply_oxygen_auth_mod_when_approve_fails(self):
        '''Paypal redirect reply (GET) fails on Oxygen's Auth Moderator'''

        #force approve child operation to fail, but authorize link succeeds:
        mock_oxygen, authorization_code, user, child_user, token, url_hash = self.prepare_paypal_reply()
        mock_oxygen.remove_mock_user(child_user.oxygen_id)

        r = get_redis_connection('default')
        r.hdel(RedisAuthentication.REDIS_AUTH_PREFIX + url_hash, 'temp_child_id')

        resp = self.client.get(
            reverse('api:verify-adult-2nd-stage', kwargs={'hash': url_hash}),
            {
                'token': token,
            },
        )

        # Request returned error.
        self.assertEqual(resp.status_code, 302)
        self.assertIn(settings.IGNITE_FRONT_END_MODERATION_URL, resp.url)
        self.assertIn('error', resp.url)
        self.assertIn('success', resp.url)
        self.assertNotIn('verifiedAuthorizationCode', resp.url)

        # Check that user is adult.
        user_after = get_user_model().objects.get(id=user.id)
        self.assertTrue(user_after.is_verified_adult)

        # Check that child is not verified.
        child_after = get_user_model().objects.get(id=child_user.id)
        self.assertFalse(child_after.is_approved)

        # Check that 'user' is the child's guardian.
        self.assertIn(
            user.id,
            list(child_after.guardians.all().values_list('id', flat=True)),
        )

    @httpretty.activate
    @patch_redis
    def test_auth_child(self):
        '''POST to auth_child that succeeds'''

        session_id = 'just-a-session-id'
        secure_session_id = 'just-a-secure-session-id'
        user = get_user_model().objects.filter(
            is_verified_adult=True, is_child=False,
        ).first()

        mock_oxygen, authorization_code, user, child_user, token, url_hash = self.prepare_child_authorization(
            user=user
        )
        self.client.force_authenticate(user)

        r = get_redis_connection('default')
        all_keys = r.keys()

        resp = self.client.post(
            reverse('api:verify-adult'),
            {
                'sessionId': session_id,
                'secureSessionId': secure_session_id,
                'authorizationCode': authorization_code,
            },
        )

        # Request successful
        self.assertEqual(resp.status_code, 200)
        self.assertIn('verifiedAuthCode', resp.data)
        self.assertEqual(resp.data['verifiedAuthCode'], authorization_code)

        new_keys = [k for k in r.keys() if k not in all_keys]

        # Check Redis key expires in 1 hour
        self.assertEqual(len(new_keys), 1)
        self.assertIn(RedisAuthentication.REDIS_AUTH_PREFIX, new_keys[0])
        self.assertLessEqual(r.ttl(new_keys[0]), 60*60)

        # Check temp_child_id in Redis
        self.assertEqual(r.hget(new_keys[0], 'temp_child_id'), str(child_user.id))

        # Check that user is adult.
        user_after = get_user_model().objects.get(id=user.id)
        self.assertTrue(user_after.is_verified_adult)

        # Check that child is verified.
        child_after = get_user_model().objects.get(id=child_user.id)
        self.assertTrue(child_after.is_approved)

        # Check that 'user' is the child's guardian.
        self.assertIn(
            user.id,
            list(child_after.guardians.all().values_list('id', flat=True)),
        )

    @httpretty.activate
    @patch_redis
    def test_auth_child_failure(self):
        '''POST to auth_child that fails on Oxygen API'''

        session_id = 'just-a-session-id'
        secure_session_id = 'just-a-secure-session-id'

        #force approve child operation to fail, but authorize link succeeds:
        user = get_user_model().objects.filter(
            is_verified_adult=True, is_child=False,
        ).first()
        mock_oxygen, authorization_code, user, child_user, token, url_hash = self.prepare_child_authorization(
            user=user,
        )
        mock_oxygen.remove_mock_user(child_user.oxygen_id)

        self.client.force_authenticate(user)

        r = get_redis_connection('default')
        all_keys = r.keys()

        resp = self.client.post(
            reverse('api:verify-adult'),
            {
                'sessionId': session_id,
                'secureSessionId': secure_session_id,
                'authorizationCode': authorization_code,
            },
        )

        # Request not-successful
        self.assertEqual(resp.status_code, 400)
        self.assertNotIn('verifiedAuthCode', resp.data)
        self.assertIn('errors', resp.data)
        self.assertIn('non_field_errors', resp.data['errors'])

        new_keys = [k for k in r.keys() if k not in all_keys]

        # Check Redis key expires in 1 hour
        self.assertEqual(len(new_keys), 1)
        self.assertIn(RedisAuthentication.REDIS_AUTH_PREFIX, new_keys[0])
        self.assertLessEqual(r.ttl(new_keys[0]), 60*60)

        # Check temp_child_id in Redis
        self.assertEqual(r.hget(new_keys[0], 'temp_child_id'), str(child_user.id))

        # Check that user is adult.
        user_after = get_user_model().objects.get(id=user.id)
        self.assertTrue(user_after.is_verified_adult)

        # Check that 'user' is the child's guardian.
        child_after = get_user_model().objects.get(id=child_user.id)
        self.assertIn(
            user.id,
            list(child_after.guardians.all().values_list('id', flat=True)),
        )

        # Check that child is NOT verified.
        self.assertFalse(child_after.is_approved)

    def test_my_children_list(self):
        '''Tests that can get list of my own children.'''
        #check GET - unauthenticated:
        self.client.force_authenticate(None)
        resp = self.client.get(reverse('api:my-children'))
        self.assertEqual(resp.status_code, 401)

        #check GET - authenticated adults:
        for guardian in get_user_model().objects.filter(is_child=False):
            self.client.force_authenticate(guardian)
            resp = self.client.get(reverse('api:my-children'))
            self.assertEqual(resp.status_code, 200)
            self.assertSetEqual(set([x['id'] for x in resp.data['results']]), set([x.id for x in guardian.children.all()]))

            for ch in resp.data['results']:
                resp2 = self.client.get(reverse('api:my-children-detail', kwargs={'child_pk': ch['id']}))
                self.assertEqual(resp2.status_code, 200)
                self.assertEqual(resp2.data, ch)
            for ch in get_user_model().objects.exclude(pk__in=guardian.children.all())[:3]:
                resp3 = self.client.get(reverse('api:my-children-detail', kwargs={'child_pk': ch.id}))
                self.assertEqual(resp3.status_code, 404)

    @httpretty.activate
    def test_add_children_to_me(self):
        #get guardian:
        guardian_obj = get_user_model().objects.annotate(
            num_cls=Count('authored_classrooms')
        ).filter(num_cls__gte=1).first() or IgniteUser.objects.filter(is_child=False).first()
        guardian_children_ids = [x.id for x in guardian_obj.children.all()]

        #check GET - authorized:
        self.client.force_authenticate(guardian_obj)
        resp = self.client.get(reverse('api:my-children'))
        self.assertEqual(resp.status_code, 200)
        self.assertSetEqual(set(guardian_children_ids), set([x['id'] for x in resp.data['results']]))

        #get children that are invitees of the guardian:
        success_children_expected = list(IgniteUser.objects.filter(
            is_child=True,
        ).exclude(
            pk__in=guardian_obj.children.all(),
        ))
        fail_children_with_adult = success_children_expected + list(IgniteUser.objects.filter(
            is_child=False
        ).exclude(
            pk=guardian_obj.pk
        )[:1])
        fail_children_with_existing_child = success_children_expected + list(guardian_obj.children.all()[:1])

        #initialize mock of Oxygen:
        mock_oxygen = MockOxygen()
        all_children_dict = {x.pk: x for x in success_children_expected + fail_children_with_adult + fail_children_with_existing_child}
        for ch in all_children_dict.values():
            mock_oxygen.set_mock_user_as_instance(ch)
        mock_oxygen.set_mock_user_as_instance(guardian_obj)
        mock_oxygen.mock_oxygen_operations(['add_moderator_children'])

        def post_add_new_children(children_list, success_expected_list):
            #check POST - authorized:
            self.client.force_authenticate(guardian_obj)
            resp = self.client.post(
                reverse('api:my-children'),
                data=json.dumps([
                    {
                        'id': x.id,
                        'moderatorType': ChildGuardian.MODERATOR_TYPE_CHOICES[x.id % len(ChildGuardian.MODERATOR_TYPE_CHOICES)][0],
                    }
                    for x in children_list
                ]),
                content_type='application/json',
            )
            if success_expected_list is not None:
                self.assertIn(resp.status_code, [200, 201])
                self.assertSetEqual(set([x.id for x in success_expected_list]), set([x['id'] for x in resp.data]))
                guardian_children_ids_new = [x.id for x in guardian_obj.children.all()]
                self.assertEqual(len(guardian_children_ids_new), len(guardian_children_ids)+len(success_expected_list))
                for child_success_resp in resp.data:
                    self.assertNotIn(child_success_resp['id'], guardian_children_ids)
                    self.assertIn(child_success_resp['id'], guardian_children_ids_new)
            else:
                self.assertEqual(resp.status_code, 400)

        #check fail children list:
        post_add_new_children(fail_children_with_adult, None)
        post_add_new_children(fail_children_with_existing_child, None)

        #check success children list:
        post_add_new_children(success_children_expected, success_children_expected)

    def test_my_students_list(self):
        '''Lists all my students in any of my authored classrooms'''
        teacher = get_user_model().objects.annotate(num_of_students=Count('authored_classrooms__students')).filter(num_of_students__gte=2).order_by('-num_of_students').first()
        students = list(get_user_model().objects.filter(classrooms__in=teacher.authored_classrooms.all()).distinct('pk'))
        students_hash = {x.id:x for x in students}

        self.client.force_authenticate(teacher)
        resp = self.client.get(reverse('api:my-students'))
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.data['count'], 2)
        self.assertEqual(resp.data['count'], len(students))

        for stud in resp.data['results']:
            self.assertIn(stud['id'], students_hash)
            self.assertIn('studentClassroomStates', stud)
            stud_teacher_classrooms = students_hash[stud['id']].classrooms_states.filter(classroom__in=teacher.authored_classrooms.all())
            stud_teacher_classrooms_hash = {x.classroom_id:x for x in stud_teacher_classrooms}
            self.assertEqual(len(stud['studentClassroomStates']), stud_teacher_classrooms.count())
            for stud_classroom_state in stud['studentClassroomStates']:
                self.assertEqual(stud_classroom_state['status'], stud_teacher_classrooms_hash[stud_classroom_state['classroomId']].status)

            resp2 = self.client.get(reverse('api:my-students-detail', kwargs={'student_pk': stud['id']}))
            self.assertEqual(resp2.status_code, 200)
            self.assertEqual(resp2.data, stud)

        for usr in get_user_model().objects.exclude(classrooms__in=teacher.authored_classrooms.all())[:3]:
            resp3 = self.client.get(reverse('api:my-students-detail', kwargs={'student_pk': usr.id}))
            self.assertEqual(resp3.status_code, 404)

    def test_my_students_list_omit(self):
        '''Lists all students that are not in a specific classroom, even if enrolled to another classroom'''
        teacher = get_user_model().objects.annotate(num_of_students=Count('authored_classrooms__students')).filter(num_of_students__gte=2).order_by('-num_of_students').first()
        students = list(get_user_model().objects.filter(classrooms__in=teacher.authored_classrooms.all()).distinct('pk'))
        students_hash = {x.id:x for x in students}

        self.client.force_authenticate(teacher)
        resp = self.client.get(reverse('api:my-students'))
        self.assertEqual(resp.status_code, 200)

        omit_student_classroom = None
        for stud in resp.data['results']:
            if len(stud['studentClassroomStates']) > 1:
                omit_student_classroom = stud['studentClassroomStates'][0]['classroomId']
                break
        if not omit_student_classroom:
            return

        resp = self.client.get(reverse('api:my-students'), {'studentClassroom!': omit_student_classroom, 'omitStudent': 'true'})
        self.assertEqual(resp.status_code, 200)
        for stud in resp.data['results']:
            self.assertFalse(students_hash[stud['id']].classrooms_states.filter(classroom=omit_student_classroom).exists())

    @httpretty.activate
    def test_my_students_list_bulk_change_status(self):
        '''Bulk change students statuses'''
        teacher = get_user_model().objects.annotate(num_of_students=Count('authored_classrooms__students')).filter(num_of_students__gte=2).order_by('-num_of_students').first()
        students = get_user_model().objects.filter(classrooms__in=teacher.authored_classrooms.all()).distinct('pk')

        #add 2 students as pending:
        pending_students = get_user_model().objects.exclude(pk__in=students).exclude(pk=teacher.pk)[0:2]
        pending_students_ids = [x.id for x in pending_students]
        for pending_stud in pending_students:
            ClassroomState(
                user=pending_stud,
                classroom=teacher.authored_classrooms.first(),
                status=ClassroomState.PENDING_STATUS,
            ).save()

        self.client.force_authenticate(teacher)
        resp = self.client.get(reverse('api:my-students'))
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.data['count'], 2)

        mock_oxygen = MockOxygen()
        mock_oxygen.mock_oxygen_operations(['add_moderator_children'])
        mock_oxygen.set_mock_user_as_instance(teacher)
        for pending_stud in pending_students:
            mock_oxygen.set_mock_user_as_instance(pending_stud)

        for stud in resp.data['results']:
            if stud['id'] in pending_students_ids:
                for pending_stud_state in stud['studentClassroomStates']:
                    self.assertEqual(pending_stud_state['status'], ClassroomState.PENDING_STATUS)
                    pending_stud_state['status'] = ClassroomState.APPROVED_STATUS
        resp2 = self.client.patch(
            reverse('api:my-students'),
            data=json.dumps(resp.data['results'], cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp2.status_code, 200)
        for stud in resp.data['results']:
            if stud['id'] in pending_students_ids:
                for pending_stud_state in stud['studentClassroomStates']:
                    self.assertEqual(pending_stud_state['status'], ClassroomState.APPROVED_STATUS)

    def test_my_users_list(self):
        '''Tests that can get list of my own users (children and students).'''
        #check GET - unauthenticated:
        self.client.force_authenticate(None)
        resp = self.client.get(reverse('api:my-users'))
        self.assertEqual(resp.status_code, 401)

        #check GET - authenticated adults:
        for user in get_user_model().objects.filter(is_child=False):
            self.client.force_authenticate(user)
            resp = self.client.get(reverse('api:my-users'))
            self.assertEqual(resp.status_code, 200)
            users_qs = get_user_model().objects.filter(
                Q(pk__in=user.children.all()) |
                Q(classrooms__in=user.authored_classrooms.all())
            )
            self.assertSetEqual(set([x['id'] for x in resp.data['results']]), set([x.id for x in users_qs]))

            for usr in resp.data['results']:
                resp2 = self.client.get(reverse('api:my-users-detail', kwargs={'user_pk': usr['id']}))
                self.assertEqual(resp2.status_code, 200)
                self.assertEqual(resp2.data, usr)
            for usr in get_user_model().objects.exclude(pk__in=users_qs)[:3]:
                resp3 = self.client.get(reverse('api:my-users-detail', kwargs={'user_pk': usr.id}))
                self.assertEqual(resp3.status_code, 404)

    @httpretty.activate
    def test_child_login_sync_approved_status_from_oxygen(self):
        '''When a child user is logged into the system, then synchronize her approved status from Oxygen.'''
        #get not approved child and her token:
        child = get_user_model().objects.filter(is_child=True, is_approved=False).first()
        child_token, _ = Token.objects.get_or_create(user=child)

        #mock this URL only to make it past (data returned is not used in this test):
        session_id = 'D81500AC-08A4-477E-9705-DCC0D4D80869'
        secure_session_id = 'W1EFBFE7B31CCWE152EE7CB18A0B54D6'
        member_data = {
            'member_id': child.member_id,
            'email': child.email,
            'name': child.name,
            'first_name': child.short_name,
            'age': 5,
            'oxygen_id': child.oxygen_id,
            'avatar': child.avatar,
            'parent_email': child.parent_email,
        }
        MockSparkDriveApi.mock_spark_drive_token(session_id, secure_session_id)
        MockSparkDriveApi.mock_spark_drive_member(member_data)

        mock_oxygen = MockOxygen()
        mock_oxygen.set_mock_user(child.oxygen_id, {
            'is_child': True,
            'is_approved': True,
        })
        mock_oxygen.mock_oxygen_operations(['get_child_status', 'get_child_moderators_all'])

        mock_redirect = settings.IGNITE_FRONT_END_BASE_URL + 'fake/path/'
        resp = self.client.get(
            reverse('api:spark-login-handler', kwargs={'redirect': mock_redirect}),
            data={'tokenkey': 'mytokenkey'},
        )

        self.assertRedirects(
            resp,
            mock_redirect + '?' + urllib.urlencode({
                    'sessionId': session_id,
                    'secureSessionId': secure_session_id,
                    'apiToken': child_token.key,
                }),
            fetch_redirect_response=False
        )

        child_after = get_user_model().objects.get(pk=child.pk)
        self.assertTrue(child_after.is_approved)

    @httpretty.activate
    def test_child_login_sync_guardians_list_from_oxygen(self):
        '''When a child user is logged into the system, then synchronize her guardians list from Oxygen.'''
        #get a child with guardians and her token:
        child = get_user_model().objects.annotate(num_guardians=Count('guardians')).filter(
            is_child=True,
            num_guardians__gte=1,
        ).first()
        child_token, _ = Token.objects.get_or_create(user=child)

        #mock this URL only to make it past (data returned is not used in this test):
        session_id = 'D81500AC-08A4-477E-9705-DCC0D4D80869'
        secure_session_id = 'W1EFBFE7B31CCWE152EE7CB18A0B54D6'
        member_data = {
            'member_id': child.member_id,
            'email': child.email,
            'name': child.name,
            'first_name': child.short_name,
            'age': 5,
            'oxygen_id': child.oxygen_id,
            'avatar': child.avatar,
            'parent_email': child.parent_email,
        }
        MockSparkDriveApi.mock_spark_drive_token(session_id, secure_session_id)
        MockSparkDriveApi.mock_spark_drive_member(member_data)

        #mock Oxygen - add new guardian, remove old guardian, add new guardian not in Ignite system:
        mock_oxygen = MockOxygen()
        mock_oxygen.mock_oxygen_operations(['get_child_status', 'get_child_moderators_all'])
        mock_oxygen.set_mock_user_as_instance(child)
        #remove 1 moderator of the child:
        for child_guardian in child.guardians.all()[1:]:
            mock_oxygen.set_mock_user_as_instance(child_guardian)
        #add new guardian (existing in Ignite system):
        new_guardian = get_user_model().objects.exclude(pk__in=child.guardians.all()).filter(is_child=False).first()
        mock_oxygen.set_mock_user_as_instance(new_guardian)
        new_guardian_oxygen = mock_oxygen.get_mock_user(new_guardian.oxygen_id)
        new_guardian_oxygen['children'].update({
            child.oxygen_id: {
                'moderator_type': ChildGuardian.MODERATOR_TYPES_TO_OXYGEN[ChildGuardian.MODERATOR_EDUCATOR],
            }
        })
        #add new guardian (not existing in Ignite system):
        non_existing_guardian_ox_id = 'NewOxID'
        non_existing_guardian_member_data = {
            'member_id': '999888777',
            'email': 'new_guardian@tinkercad.com',
            'name': 'Tinkercad Guardian',
            'first_name': 'Tinkercad Guardian',
            'age': 40,
            'oxygen_id': non_existing_guardian_ox_id,
            'avatar': 'http://host.com/avatar.jpg',
        }
        mock_oxygen.set_mock_user(non_existing_guardian_ox_id, {
            'is_child': False,
            'is_approved': False,
            'is_verified_adult': True,
            'children': {
                child.oxygen_id: {
                    'moderator_type': ChildGuardian.MODERATOR_TYPES_TO_OXYGEN[ChildGuardian.MODERATOR_PARENT],
                }
            }
        })
        MockSparkDriveApi.mock_spark_drive_member_by_oxygen_id(non_existing_guardian_member_data, with_session={'session_id': session_id})

        mock_redirect = settings.IGNITE_FRONT_END_BASE_URL + 'fake/path/'
        resp = self.client.get(
            reverse('api:spark-login-handler', kwargs={'redirect': mock_redirect}),
            data={'tokenkey': 'mytokenkey'},
        )

        self.assertRedirects(
            resp,
            mock_redirect + '?' + urllib.urlencode({
                    'sessionId': session_id,
                    'secureSessionId': secure_session_id,
                    'apiToken': child_token.key,
                }),
            fetch_redirect_response=False
        )

        #check that child's guardians are synchronized with Oxygen:
        self.assertDictEqual(
            {x.guardian.oxygen_id: ChildGuardian.MODERATOR_TYPES_TO_OXYGEN[x.moderator_type] for x in child.childguardian_guardian_set.all()},
            {x: mock_oxygen.get_mock_user(x)['children'].get(child.oxygen_id)['moderator_type'] for x in mock_oxygen.get_child_moderators_list(child.oxygen_id)}
        )

    @httpretty.activate
    def test_verified_adult_login_sync_children_list_from_oxygen(self):
        '''When a verified adult user is logged into the system, then synchronize her children list from Oxygen.'''
        #get not adult with children and her token (make sure to set her as verified adult):
        verified_adult = get_user_model().objects.annotate(num_children=Count('children')).filter(is_child=False, num_children__gte=2).first()
        verified_adult.is_verified_adult = True
        verified_adult.save()
        verified_adult_token, _ = Token.objects.get_or_create(user=verified_adult)

        #mock this URL only to make it past (data returned is not used in this test):
        session_id = 'A81500AC-08A4-477E-9705-ACC0A4D80869'
        secure_session_id = 'X1EFBFE7B31CCXE152EE7CB18A0B54D6'
        member_data = {
            'member_id': verified_adult.member_id,
            'email': verified_adult.email,
            'name': verified_adult.name,
            'first_name': verified_adult.short_name,
            'age': 28,
            'oxygen_id': verified_adult.oxygen_id,
            'avatar': verified_adult.avatar,
        }
        MockSparkDriveApi.mock_spark_drive_token(session_id, secure_session_id)
        MockSparkDriveApi.mock_spark_drive_member(member_data)

        #mock Oxygen of verified adult with some children:
        mock_oxygen = MockOxygen()
        mock_oxygen.mock_oxygen_operations(['get_moderator_children_all'])
        mock_oxygen.set_mock_user_as_instance(verified_adult)
        verified_adult_oxygen = mock_oxygen.get_mock_user(verified_adult.oxygen_id)
        verified_adult_oxygen['children'] = {}  #reset user's oxygen children
        #keep 1 existing child, but change her moderation type
        existing_child_link_to_keep = verified_adult.childguardian_child_set.all()[0]
        verified_adult_oxygen['children'][existing_child_link_to_keep.child.oxygen_id] = {
            'moderator_type': ChildGuardian.MODERATOR_TYPES_TO_OXYGEN[ChildGuardian.MODERATOR_EDUCATOR if existing_child_link_to_keep.moderator_type==ChildGuardian.MODERATOR_PARENT else ChildGuardian.MODERATOR_PARENT]
        }
        #add some new oxygen children
        new_oxygen_children = get_user_model().objects.filter(is_child=True).exclude(pk__in=verified_adult.children.all())[:2]
        for new_oxygen_child in new_oxygen_children:
            mock_oxygen.set_mock_user_as_instance(new_oxygen_child)
            verified_adult_oxygen['children'].update({
                new_oxygen_child.oxygen_id: {
                    'moderator_type': ChildGuardian.MODERATOR_TYPES_TO_OXYGEN[ChildGuardian.MODERATOR_PARENT],
                }
            })

        mock_redirect = settings.IGNITE_FRONT_END_BASE_URL + 'fake/path/'
        resp = self.client.get(
            reverse('api:spark-login-handler', kwargs={'redirect': mock_redirect}),
            data={'tokenkey': 'mytokenkey'},
        )

        self.assertRedirects(
            resp,
            mock_redirect + '?' + urllib.urlencode({
                    'sessionId': session_id,
                    'secureSessionId': secure_session_id,
                    'apiToken': verified_adult_token.key,
                }),
            fetch_redirect_response=False
        )

        #check that guardian's children are synchronized with Oxygen:
        self.assertDictEqual(
            {x.child.oxygen_id: ChildGuardian.MODERATOR_TYPES_TO_OXYGEN[x.moderator_type] for x in verified_adult.childguardian_child_set.all()},
            {ch_id: ch_oxygen['moderator_type'] for ch_id, ch_oxygen in verified_adult_oxygen['children'].items()}
        )

    # Default Avatar - Conversion to HTTPS
    # ####################################

    @override_settings(DEFAULT_USER_AVATAR='')
    @httpretty.activate
    def test_default_avatar_converts_to_https(self):
        """Check that the default avatar is converted into HTTPS"""

        session_id = '281500AC-08A4-477E-9705-2CC024D80869'
        secure_session_id = '21EFBFE7B31CC2E152EE7CB18A0B54D6'

        member_data = {
            'member_id': "281500AC-08A4-477E-9705-2CC024D80869",
            'email': 'o@o.com',
            'name': 'Ofir Ovadia',
            'first_name': 'Ofir',
            'age': 20,
            'oxygen_id': 'u98345934u590j1f',
            'avatar': 'http://alpha.jlaskdfj19http.comhttp:80/Images/v23/Member/default_avatar.png',
        }
        MockSparkDriveApi.mock_spark_drive_member(member_data)

        resp = self.client.post(reverse('api:get-auth-token'), {
            'sessionId': session_id,
            'secureSessionId': secure_session_id
        })

        self.assertEqual(resp.status_code, 200)
        self.assertIn('token', resp.data)
        db_user = get_user_model().objects.get(auth_token__key=resp.data['token'])
        self.assertEqual(db_user.avatar, member_data['avatar'].replace('http://', 'https://'))

    @override_settings(DEFAULT_USER_AVATAR='https://www.placekitten.com/50/50')
    @httpretty.activate
    def test_default_avatar_converts_to_settings_override(self):
        """Check that the default avatar is converted into HTTPS"""

        session_id = '281500AC-08A4-477E-9705-2CC024D80869'
        secure_session_id = '21EFBFE7B31CC2E152EE7CB18A0B54D6'

        member_data = {
            'member_id': "281500AC-08A4-477E-9705-2CC024D80869",
            'email': 'o@o.com',
            'name': 'Ofir Ovadia',
            'first_name': 'Ofir',
            'age': 20,
            'oxygen_id': 'u98345934u590j1f',
            'avatar': 'http://alpha.jlaskdfj19http.comhttp:80/Images/v23/Member/default_avatar.png',
        }
        MockSparkDriveApi.mock_spark_drive_member(member_data)

        resp = self.client.post(reverse('api:get-auth-token'), {
            'sessionId': session_id,
            'secureSessionId': secure_session_id
        })

        self.assertEqual(resp.status_code, 200)
        self.assertIn('token', resp.data)
        db_user = get_user_model().objects.get(auth_token__key=resp.data['token'])
        self.assertEqual(db_user.avatar, 'https://www.placekitten.com/50/50')

    @override_settings(DEFAULT_USER_AVATAR='')
    @httpretty.activate
    def test_non_default_avatar_stays_the_same(self):
        """If the avatar is a custom avatar, we shouldn't mess with it"""

        session_id = '281500AC-08A4-477E-9705-2CC024D80869'
        secure_session_id = '21EFBFE7B31CC2E152EE7CB18A0B54D6'

        member_data = {
            'member_id': "281500AC-08A4-477E-9705-2CC024D80869",
            'email': 'o@o.com',
            'name': 'Ofir Ovadia',
            'first_name': 'Ofir',
            'age': 20,
            'oxygen_id': 'u98345934u590j1f',
            'avatar': 'http://alpha.jlaskdfj19http.comhttp:80/Images/v23/Member/non_default_avatar.png',
        }
        MockSparkDriveApi.mock_spark_drive_member(member_data)

        resp = self.client.post(reverse('api:get-auth-token'), {
            'sessionId': session_id,
            'secureSessionId': secure_session_id
        })

        self.assertEqual(resp.status_code, 200)
        self.assertIn('token', resp.data)
        db_user = get_user_model().objects.get(auth_token__key=resp.data['token'])
        self.assertEqual(db_user.avatar, member_data['avatar'])
        self.assertTrue(db_user.avatar.startswith('http://'))

    @override_settings(DEFAULT_USER_AVATAR='https://www.placekitten.com/50/50')
    @httpretty.activate
    def test_non_default_avatar_stays_the_same_when_avatar_override_is_set(self):
        """If the avatar is a custom avatar, we shouldn't mess with it"""

        session_id = '281500AC-08A4-477E-9705-2CC024D80869'
        secure_session_id = '21EFBFE7B31CC2E152EE7CB18A0B54D6'

        member_data = {
            'member_id': "281500AC-08A4-477E-9705-2CC024D80869",
            'email': 'o@o.com',
            'name': 'Ofir Ovadia',
            'first_name': 'Ofir',
            'age': 20,
            'oxygen_id': 'u98345934u590j1f',
            'avatar': 'http://alpha.jlaskdfj19http.comhttp:80/Images/v23/Member/non_default_avatar.png',
        }
        MockSparkDriveApi.mock_spark_drive_member(member_data)

        resp = self.client.post(reverse('api:get-auth-token'), {
            'sessionId': session_id,
            'secureSessionId': secure_session_id
        })

        self.assertEqual(resp.status_code, 200)
        self.assertIn('token', resp.data)
        db_user = get_user_model().objects.get(auth_token__key=resp.data['token'])
        self.assertEqual(db_user.avatar, member_data['avatar'])
        self.assertTrue(db_user.avatar.startswith('http://'))

    @override_settings(DEFAULT_USER_AVATAR='')
    @httpretty.activate
    def test_default_avatar_already_https_stays_same(self):
        """If default avatar is HTTPS, then it shouldn't be affected"""

        session_id = '281500AC-08A4-477E-9705-2CC024D80869'
        secure_session_id = '21EFBFE7B31CC2E152EE7CB18A0B54D6'

        member_data = {
            'member_id': "281500AC-08A4-477E-9705-2CC024D80869",
            'email': 'o@o.com',
            'name': 'Ofir Ovadia',
            'first_name': 'Ofir',
            'age': 20,
            'oxygen_id': 'u98345934u590j1f',
            'avatar': 'https://alpha.jlaskdfj19http.comhttp:80/Images/v23/Member/default_avatar.png',
        }
        MockSparkDriveApi.mock_spark_drive_member(member_data)

        resp = self.client.post(reverse('api:get-auth-token'), {
            'sessionId': session_id,
            'secureSessionId': secure_session_id
        })

        self.assertEqual(resp.status_code, 200)
        self.assertIn('token', resp.data)
        db_user = get_user_model().objects.get(auth_token__key=resp.data['token'])
        self.assertEqual(db_user.avatar, member_data['avatar'])
        self.assertTrue(db_user.avatar.startswith('https://'))

