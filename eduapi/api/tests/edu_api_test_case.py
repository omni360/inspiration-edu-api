import json
import copy

from django.db.models import Count
from django.contrib.auth import get_user_model
from django.core.serializers.json import DjangoJSONEncoder

from rest_framework import serializers

from api_test_case.api_test_case import ApiTestCase
from api_test_case.decorators import should_check_action

from api.models import Project
from api.serializers.fields import InlineListRelatedField
from .utils.queriesnumtrace import QueriesNumTestCase
from .base_test_case import BaseTestCase

class EduApiTestCase(ApiTestCase, BaseTestCase, QueriesNumTestCase):

    def setUp(self):

        super(EduApiTestCase, self).setUp()
        BaseTestCase.setUp(self) # Call BaseTestCase's setUp explicitly, because super calls ApiTestCase's

        self.inline_fields = [
            fn 
            for fn, f 
            in self.serializer().get_fields().items()
            if isinstance(f, InlineListRelatedField)
        ]

        self.choice_fields = [
            fn 
            for fn, f 
            in self.serializer().get_fields().items()
            if isinstance(f, serializers.ChoiceField)
        ]

        self.image_fields = [
            fn 
            for fn, f 
            in self.serializer().get_fields().items()
            if 'image' in fn.lower() or fn.lower() == 'avatar'
        ]

    def check_choices_on_options_response(self, choice_fields, resp):
        self.assertIn(resp.status_code, xrange(200, 205))

        if resp.data.get('actions', {}).get('GET', False):
            meta = resp.data['actions']['GET']

            for field_name in choice_fields:

                self.assertIn(field_name, meta)
                self.assertIn('choices', meta[field_name])
                self.assertGreaterEqual(meta[field_name]['choices'], 1)

    @should_check_action(actions_tested=('update'))
    def test_inline_fields_dont_duplicate(self, obj_list=None):
        '''
        Make sure that for every inline field, if you save an object that
        already has a value in the list, the list will not get bigger and bigger.

        This is a result of a bug that was found with the teachersFiles of Project.
        The Project already had teachersFiles, whenever the Project was saved,
        all of the files were duplicated.
        '''

        for api_field_name in self.inline_fields:

            db_field_name = self.to_snake_case(api_field_name)

            # Get an object with at least 1 item in the field_name list
            obj_list = obj_list if obj_list is not None else self.all_user_objects
            obj = obj_list.annotate(
                inline_num=Count(db_field_name)
            ).filter(inline_num__gte=1)[0]

            # Get the object from the API
            api_obj = self.client.get(
                self.get_api_details_url(obj)
            ).data

            # PUT the object back
            resp2 = self.client.put(
                api_obj['self'],
                json.dumps(api_obj, cls=DjangoJSONEncoder),
                content_type='application/json'
            )

            self.assertIn(resp2.status_code, xrange(200,205))

            # Make sure that the list is still the same size
            self.assertListEqual(
                resp2.data[api_field_name],
                api_obj[api_field_name]
            )

    def test_get_choices_on_options_without_login(self):
        '''
        Test that the user can get the available choices for all fields
        even if not logged in.
        '''
        if not self.with_choices_on_get:
            return

        if self.allow_unauthenticated_get:
            self.client.force_authenticate(None)

        resp = self.client.options(self.api_list_url)

        self.check_choices_on_options_response(self.choice_fields, resp)

    @should_check_action(actions_tested=('create',))
    def test_save_images_with_spaces(self):
        '''
        For bug #45: When an image has a space in its name, the API returns 400.
        Since inkFilePicker and the browsers can all handle images with spaces
        in their name, it seems appropriate that the server will be able to
        handle them as well. This test makes sure that the server can handle 
        such images (it escapes them).
        '''

        obj = copy.deepcopy(self.object_to_post)
        if not obj:
            return
        url_with_spaces = 'http://example.com/image with spaces'

        for api_field_name in self.image_fields:

            db_field_name = self.to_snake_case(api_field_name)
            
            obj[api_field_name] = url_with_spaces

            resp = self.client.post(self.api_list_url, json.dumps(
                obj, cls=DjangoJSONEncoder
            ), content_type='application/json')

            self.assertIn(resp.status_code, xrange(200, 205))
            self.assertIn(api_field_name, resp.data)

    @should_check_action(actions_tested=('create',))
    def test_save_images_with_none(self):
        '''
        Test that if image gets a non-string value (e.g. None), the save 
        operation doesn't fail.
        '''

        obj = copy.deepcopy(self.object_to_post)
        if not obj:
            return

        for api_field_name in self.image_fields:

            db_field_name = self.to_snake_case(api_field_name)
            
            obj[api_field_name] = None

            resp = self.client.post(self.api_list_url, json.dumps(
                obj, cls=DjangoJSONEncoder
            ), content_type='application/json')

            self.assertIn(resp.status_code, xrange(200, 205))
            self.assertFalse(resp.data[api_field_name])

    def test_object_has_self_field(self):
        '''
        Makes sure that the details and list objects have a 'self' attribute.

        The self attribute should be a link to the object.
        '''

        # Make sure that when we call the list API, every object in the list
        # has a self attribute.
        api_objects = self.client.get(self.api_list_url).data['results']
        for obj in api_objects:
            self.assertIn('self', obj)

        # Call one of the objects' self URL
        api_obj = api_objects[0]
        api_obj2 = self.client.get(api_obj['self']).data

        # Make sure that the returned object has the same self URL as the 
        # called object.
        self.assertEqual(api_obj2['self'], api_obj['self'])

    def test_cant_make_unsafe_actions_if_not_logged_in(self):
        '''
        Test that a non-logged-in user can't POST\PUT\PATCH\DELETE.
        '''

        self.client.force_authenticate(None)

        details_url = self.get_api_details_url(self.all_user_objects.first())

        for action, url in (
            ('post', self.api_list_url),
            ('put', details_url),
            ('patch', details_url),
            ('delete', details_url),
        ):

            resp = getattr(self.client, action)(
                url, '{}', content_type='application/json'
            )

            # Either the action is not permitted at all or the user 
            # should be authenticated.
            self.assertIn(resp.status_code, [401, 405])

    @should_check_action(actions_tested=('delete',))
    def test_cant_delete_if_not_owner(self):
        '''
        Test that a user who's not the owner can't DELETE an object.
        '''

        if not hasattr(self.all_user_objects.first(), 'owner'):
            return

        for db_obj in self.all_user_objects:

            for user in get_user_model().objects.all():

                if user == db_obj.owner or (user in db_obj.owner.guardians.all()):
                    continue

                self.client.force_authenticate(user)

                resp = self.client.delete(
                    self.get_api_details_url(db_obj),
                )

                self.assertIn(resp.status_code, [401,404,403])
