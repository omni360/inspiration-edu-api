import copy
import json
import random
import unittest
import urllib

from django.core.exceptions import ObjectDoesNotExist
from django.core.serializers.json import DjangoJSONEncoder
from rest_framework.serializers import Serializer
from api.models import Review
from utils_app.models import DeleteStatusModel

from .decorators import should_check_action


class ApiListTestCase(object):
    def test_get_list(self, api_list_url=None, db_objs=None):
        '''
        Makes sure that the get_list API works as expected
        '''
        api_list_url = api_list_url if api_list_url is not None else self.api_list_url
        db_objs = db_objs if db_objs is not None else self.all_user_objects

        resp = self.client.get(api_list_url + '?pageSize=' + str(db_objs.count()))

        # Succeeded
        self.assertEqual(resp.status_code, 200)

        data = resp.data

        # General Structure
        self.assertIn('results', data)
        self.assertIn('previous', data)
        self.assertIn('next', data)
        self.assertIn('count', data)

        self.assertEqual(data['count'], db_objs.count(), msg='List "%s" did not return all_user_objects count.' % api_list_url)

        self.compare_db_obj_list_with_api(db_objs, data['results'])

    def test_get_list_all_fields_are_present(self):
        '''
        Tests that the API returns the required fields.
        '''

        data = self.client.get(self.api_list_url).data
        for field_name in self.fields:
            # we have fields that are discarded from serializers by default
            if field_name not in self.dropfields:
                self.assertIn(field_name, data['results'][0].keys())

    @unittest.skip('The logic was changed to drop some fields by default and bring back only with "embed" request')
    def test_get_list_subset_of_fields(self):
        '''
        Makes sure there's a way to get only a subset of the fields in
        the object.
        '''
        if not self.allow_subset_of_fields:
            return

        indexes = [int(random.random()*len(self.fields)) for i in xrange(4)]

        FIELDS = list(set([self.fields[idx] for idx in indexes if idx < len(self.fields)]))

        resp = self.client.get(self.api_list_url, {
            'fields': ','.join(FIELDS),
        })

        # Succeeded
        self.assertEqual(resp.status_code, 200)

        data = resp.data

        for api_obj in data['results']:

            # Make sure that only the requested fields are returned.
            for field_name in FIELDS:
                # we have fields that are discarded from serializers by default
                if field_name not in self.dropfields:
                    self.assertIn(field_name, api_obj.keys())

            fields_len = len(FIELDS)
            mirror_fields = getattr(self.serializer.Meta, 'mirror_fields', [])
            for mirror_field_source, mirror_field_target in mirror_fields:
                if mirror_field_source in api_obj.keys():
                    fields_len += 1
            self.assertEqual(fields_len, len(api_obj.keys()))

            try:
                kwargs = {
                    self.to_snake_case(key): value
                    for key, value
                    in api_obj.items()
                    if not isinstance(value, list) and
                        (type(value) == 'str' and 'http://' not in value)
                }

                if len(kwargs.keys()):
                    self.all_user_objects.filter(**kwargs)
            except ObjectDoesNotExist:
                self.fail('objects.filter(...) raised DoesNotExist unexpectedly')

    def test_get_list_by_filtering(self):
        '''
        Tests that filtering works.
        '''

        self.client.force_authenticate(self.global_user)

        for api_filters, db_filters in self.filters:

            # Should be valid
            if db_filters != 'ERROR':
                db_filters = db_filters if db_filters is not None else api_filters
                objs_from_db = self.all_user_objects.filter(**db_filters)

                resp = self.client.get(self.api_list_url, dict(
                    api_filters.items() + {'pageSize': objs_from_db.count()}.items()
                ))

                # Make sure we get the correct number of objects with duration gte to 20
                self.assertEqual(resp.status_code, 200)
                self.assertEqual(resp.data['count'], objs_from_db.count(), msg=str(api_filters))

                self.compare_db_obj_list_with_api(objs_from_db, resp.data['results'])

            # Should return error 400
            else:
                resp = self.client.get(self.api_list_url, dict(
                    api_filters.items()
                ))

                # Should return 400
                self.assertEqual(resp.status_code, 400)
                self.assertIn('filterErrors', resp.data)

    def test_get_list_pagination(self):
        '''
        Makes sure that there's a pagination option and that it works as
        expected.

        Assumptions:
            - There are more than 2 objects in the database
        '''

        if not self.pagination or not self.all_user_objects.count() > 1:
            return

        PAGE_SIZE = int(self.all_user_objects.count() / 2)

        resp = self.client.get(self.api_list_url, {'pageSize': PAGE_SIZE})

        # Succeeded
        self.assertEqual(resp.status_code, 200)

        data = resp.data

        # Make sure that count reflects the total number of objects in the database.
        self.assertEqual(self.all_user_objects.count(), data['count'])

        # The number of results should equal the page size
        self.assertEqual(PAGE_SIZE, len(data['results']))

        # Make sure that there's a next page, but not previous page
        self.assertIsNone(data['previous'])
        self.assertIsNotNone(data['next'])

    @unittest.skip('ElasticSearch')
    def test_get_list_free_text_search(self):
        '''
        Tests that searching by free text works properly.
        '''

        for field in self.free_text_fields:

            # Search for an object that contains data in the relevant field.
            try:
                obj_from_db = self.all_user_objects.exclude(**{field: ''})[0]
            except IndexError:
                continue

            # Create a search term using a subset of the field's value in an
            # existing object.
            search_term = getattr(obj_from_db, field)[3:10]

            # Search by the search_term
            resp = self.client.get(self.api_list_url, {
                'search': search_term,
            })

            # Make sure we got at least one result
            self.assertEqual(resp.status_code, 200)
            self.assertGreaterEqual(resp.data['count'], 1)

            # Make sure that all of the results are valid
            for api_obj in resp.data['results']:
                for term in search_term.split():
                    self.assertIn(term.lower(), ''.join([
                        api_obj[self.to_camel_case(x)]
                        for x
                        in self.free_text_fields
                    ]).lower())

    def test_get_list_everyone_can(self):
        if not self.allow_unauthenticated_get:
            return

        self.client.force_authenticate(None)

        self.test_get_list(None, self.all_public_objects)


class ApiRetrieveTestCase(object):
    def test_get_object(self, objs_from_db=None):
        '''
        Tests that the Object Details view works properly.
        '''

        # Note that objs_from_db might be []
        if objs_from_db == None:
            objs_from_db = self.all_user_objects

        # Check that each of the objects in the database can be accessed using
        # the object details view.
        for db_obj in objs_from_db:

            resp = self.client.get(self.get_api_details_url(db_obj))

            self.assertEqual(resp.status_code, 200)
            self.compare_db_obj_with_api(db_obj, resp.data)

    def test_get_object_everyone_can(self):
        if not self.allow_unauthenticated_get:
            return

        self.client.force_authenticate(None)

        self.test_get_object(self.all_public_objects)


class ApiCreateTestCase(object):
    def _check_equal_result(self, val_input, val_output, key, serializer):
        if isinstance(val_input, basestring):
            self.assertTrue(val_input == val_output or str(val_input) == str(val_output))
        elif isinstance(val_input, dict):
            if isinstance(serializer._declared_fields.get(key), Serializer):
                for k, v in val_input.items():
                    self._check_equal_result(v, val_output.get(k), k, serializer._declared_fields[key])
            else:
                self.assertDictEqual(val_input, val_output)
        elif isinstance(val_input, list):
            self.assertListEqual(val_input, val_output)

    def _check_saved_result(self, db_obj, val_input, key, serializer):
        db_attr_name = (serializer._declared_fields[key].source or key) if key in serializer._declared_fields else self.to_snake_case(key)
        if isinstance(val_input, basestring):
            self.assertEqual(
                str(getattr(db_obj, db_attr_name)),
                str(val_input)
            )
        elif isinstance(val_input, dict):
            if isinstance(serializer._declared_fields.get(key), Serializer):
                for k, v in val_input.items():
                    self._check_saved_result(db_obj, v, k, serializer._declared_fields[key])
            else:
                self.assertDictEqual(
                    getattr(db_obj, db_attr_name),
                    val_input
                )
        elif isinstance(val_input, list):
            self.assertListEqual(
                getattr(db_obj, db_attr_name),
                val_input
            )

    @should_check_action(actions_tested=('create',))
    def test_post_object(self):
        '''
        Tests that we can add a new object via the API.
        '''

        kwargs = copy.deepcopy(self.object_to_post)

        if not kwargs:
            return

        resp = self.client.post(self.api_list_url, json.dumps(
            kwargs,
            cls=DjangoJSONEncoder
        ), content_type='application/json')

        self.assertIn(resp.status_code, [200, 201, 202, 203])

        data = resp.data

        # Make sure that the response contains the ID (lookup_field) and that each
        # of the fields is correctly represented in the response.
        self.assertIn(self.lookup_field, data)
        for key, val in kwargs.items():
            self._check_equal_result(val, data[key], key, self.serializer)

        # Make sure that the object was properly saved in the database.
        db_obj = self.all_user_objects.get(**{self.lookup_field: data[self.lookup_field]})
        for key, val in kwargs.items():
            self._check_saved_result(db_obj, val, key, self.serializer)

        # Cleanup
        db_obj.delete()

    @should_check_action(actions_tested=('create',))
    def test_post_object_only_required_fields(self):
        '''
        Tests that we can add a new object via the API. Only the required fields.
        '''

        if not self.object_to_post:
            return

        required_fields = [
            fn
            for fn, f
            in self.serializer().get_fields().items()
            if getattr(f, 'required', False)
        ]

        kwargs = copy.deepcopy(self.object_to_post)

        for field_name in kwargs.keys():
            if field_name not in required_fields:

                del kwargs[field_name]

        resp = self.client.post(self.api_list_url, json.dumps(
            kwargs,
            cls=DjangoJSONEncoder
        ), content_type='application/json')

        self.assertIn(resp.status_code, [200, 201, 202, 203])

        data = resp.data

        # Make sure that the response contains the ID (lookup_field) and that each
        # of the fields is correctly represented in the response.
        self.assertIn(self.lookup_field, data)
        for key, val in kwargs.items():
            self.assertTrue(data[key] == val or str(data[key]) == str(val))

        # Cleanup
        db_obj = self.all_user_objects.get(**{self.lookup_field: data[self.lookup_field]})
        db_obj.delete()

    @should_check_action(actions_tested=('create',))
    def test_post_object_check_fields(self):
        for check_field in self.check_fields:
            field_name = check_field[0]
            field_success = check_field[1]
            field_input = check_field[2]
            field_output = check_field[3] if len(check_field) > 3 else None

            kwargs = copy.deepcopy(self.object_to_post)
            kwargs[field_name] = field_input

            resp = self.client.post(self.api_list_url, json.dumps(
                kwargs,
                cls=DjangoJSONEncoder
            ), content_type='application/json')

            if field_success:
                self.assertIn(resp.status_code, [200, 201])
                self.assertEqual(resp.data[field_name] if field_name in resp.data else None, field_output if field_output is not None else field_input,)
            else:
                self.assertIn(resp.status_code, [400])

    @should_check_action(actions_tested=('create',))
    def test_post_bulk_objects(self):
        '''
        Tests that we can add new objects in bulk via the API.
        '''
        if 'post' not in self.bulk_actions:
            return

        kwargs_list = []
        for i in xrange(0,3):
            kwargs = copy.deepcopy(self.object_to_post)
            if not kwargs:
                return
            kwargs_list.append(kwargs)

        resp = self.client.post(self.api_list_url, json.dumps(
            kwargs_list,
            cls=DjangoJSONEncoder
        ), content_type='application/json')

        self.assertIn(resp.status_code, [200, 201, 202, 203])

        data = resp.data

        self.assertEqual(len(data), len(kwargs_list))

        for item in data:

            self.assertIn(self.lookup_field, item)

            # Cleanup
            db_obj = self.all_user_objects.get(**{self.lookup_field: item[self.lookup_field]})
            db_obj.delete()


class ApiDeleteTestCase(object):
    @should_check_action(actions_tested=('delete',))
    def test_delete_object(self):
        '''
        Makes sure delete works properly
        '''
        object_to_delete = self.object_to_delete if self.object_to_delete is not None else self.all_user_objects[0]

        api_obj = self.client.get(self.get_api_details_url(object_to_delete)).data

        if isinstance(object_to_delete, Review):
            self.client.force_authenticate(object_to_delete.owner)
        resp = self.client.delete(self.get_api_details_url(object_to_delete))

        # Success
        self.assertEqual(resp.status_code, 204)

        # Make sure that object is no longer in DB.
        self.assertRaises(
            ObjectDoesNotExist,
            self.all_user_objects.get,
            **{self.lookup_field: getattr(object_to_delete, self.lookup_field)}
        )

        # If model has delete status, then check the instance is archived.
        if issubclass(self.all_user_objects.model, DeleteStatusModel):
            self.assertTrue(self.all_user_objects.model.objects.deleted().filter(pk=object_to_delete.pk).exists())

        # Restore the object to the DB.
        self.client.post(self.api_list_url, json.dumps(
            api_obj,
            cls=DjangoJSONEncoder
        ), content_type='application/json')

    @should_check_action(actions_tested=('delete',))
    def test_delete_object_not_existing(self):
        '''
        Makes sure delete doesn't delete anything and fails with the
        correct status code if invalid ID (lookup_field) is supplied.
        '''

        objs_in_db_before = self.all_user_objects.count()

        resp = self.client.delete(self.non_existant_obj_details_url)

        # Not Found
        self.assertEqual(resp.status_code, 404)

        # Make sure that object is no longer in DB.
        self.assertEqual(objs_in_db_before, self.all_user_objects.count())

    @should_check_action(actions_tested=('delete',))
    def test_delete_bulk_objects(self):
        '''
        Makes sure delete works in bulk mode, using idList query-param filter.
        '''
        if 'delete' not in self.bulk_actions:
            return

        object_to_delete = self.object_to_delete if self.object_to_delete is not None else self.all_user_objects[0]

        api_obj = self.client.get(self.get_api_details_url(object_to_delete)).data

        resp = self.client.delete(
            self.api_list_url + '?' + urllib.urlencode({self.lookup_field+'List': ','.join([str(object_to_delete.id), '99999'])}),
        )

        # Success
        self.assertEqual(resp.status_code, 204)

        # Make sure that object is no longer in DB.
        self.assertRaises(
            ObjectDoesNotExist,
            self.all_user_objects.get,
            **{self.lookup_field: getattr(object_to_delete, self.lookup_field)}
        )

        # Restore the object to the DB.
        self.client.post(self.api_list_url, json.dumps(
            api_obj,
            cls=DjangoJSONEncoder
        ), content_type='application/json')

    @should_check_action(actions_tested=('delete',))
    def test_delete_bulk_objects_without_explicit_list_filter_is_failing(self):
        '''
        Makes sure delete in bulk mode fails when not using idList query-param filter.
        '''
        if 'delete' not in self.bulk_actions:
            return

        object_to_delete = self.object_to_delete if self.object_to_delete is not None else self.all_user_objects[0]

        api_obj = self.client.get(self.get_api_details_url(object_to_delete)).data

        resp = self.client.delete(
            self.api_list_url,
        )

        # Bad Request
        self.assertEqual(resp.status_code, 400)

        # Make sure that object still exists in the DB.
        self.assertTrue(self.all_user_objects.filter(**{self.lookup_field: getattr(object_to_delete, self.lookup_field)}).exists())


class ApiUpdateTestCase(object):

    longMessage = True

    @should_check_action(actions_tested=('update',))
    def test_puts(self):
        
        for idx, action in enumerate(self.put_actions):

            extra_msg = 'Iteration: %s' % idx

            url = self.get_api_details_url(action['get_object']())

            api_obj = self.client.get(url).data
            object_to_put = action.get('object_to_put', copy.deepcopy(api_obj))

            url_to_put = getattr(api_obj, 'self', url)
            object_before_change = self.model.objects.get(**{
                self.lookup_field: api_obj[
                    self.to_camel_case(self.lookup_field)
                ]
            })
            # object_to_put = copy.deepcopy(object_before_change)

            # Make sure that object_to_put is a dictionary
            # if type(object_to_put) == self.model:
            #     object_to_put = self.model_to_dict(object_to_put)

            # Create object_to_put from the object_to_put.
            for field, value in action.get('updated_data', {}).items():
                object_to_put[field] = value

            # Log in and make PUT request.
            self.client.force_authenticate(action.get('user', self.global_user))
            resp = self.client.put(url_to_put, json.dumps(object_to_put, cls=DjangoJSONEncoder), content_type='application/json')

            # Get expected result.
            expected_result = action.get('expected_result', 200)
            self.assertEqual(
                resp.status_code, 
                expected_result,
                msg=extra_msg + ', response_body: %s' % resp.data
            )

            if action.get('expected_response'):
                self.assertEqual(
                    resp.data, action['expected_response'], msg=extra_msg
                )

            # If PUT successful.
            if resp.status_code == 200:

                # Make sure that the object was properly saved in the database.
                db_obj = self.model.objects.get(**{
                    self.lookup_field: object_to_put[self.lookup_field]
                })
                self.compare_db_obj_with_api(db_obj, object_to_put, msg=extra_msg)

                # Restore the object to the DB.
                object_before_change.save()
        
            self.client.force_authenticate(self.global_user)


    @should_check_action(actions_tested=('update',))
    def test_patch_object_invalid(self):

        if getattr(self, 'invalid_objects_patch', None):

            resp = self.client.get(self.get_api_details_url(self.invalid_objects_patch['get_object']()))
            default_api_obj = resp.data

            default_url_to_update = getattr(default_api_obj, 'self', self.get_api_details_url(self.invalid_objects_patch['get_object']()))

            self.client.force_authenticate(self.invalid_objects_patch['user'])

            for invalid_patch in self.invalid_objects_patch['invalid_patches']:
                url_to_update = default_url_to_update
                if 'get_object' in invalid_patch:
                    #set url_to_update from current iteration get_object function:
                    resp = self.client.get(self.get_api_details_url(invalid_patch['get_object']()))
                    api_obj = resp.data
                    url_to_update = getattr(api_obj, 'self', self.get_api_details_url(invalid_patch['get_object']()))

                if 'user' in invalid_patch:
                    #set user for current iteration:
                    self.client.force_authenticate(invalid_patch['user'])

                resp = self.client.patch(url_to_update, json.dumps(invalid_patch['data'], cls=DjangoJSONEncoder), content_type='application/json')

                if 'user' in invalid_patch:
                    #reset user to default:
                    self.client.force_authenticate(self.invalid_objects_patch['user'])

                self.assertEqual(resp.status_code, invalid_patch.get('expected_result', 400), msg=invalid_patch.get('assert_msg', None))

            self.client.force_authenticate(self.global_user)

    @should_check_action(actions_tested=('update',))
    def test_patch_object(self):
        '''
        Tests that we can edit (PATCH) an object via the API.
        field_to_patch is of the form: {'field': field_name', 'value': some_value, 'exclude': field_name},
        where "exclude" is the field to be removed from the PATCHed object (since PATCH works with partial
        objects, and doesn't require all fields).
        '''
        if not self.field_to_patch:
            return

        object_to_patch = self.all_user_objects[0]
        data = self.client.get(self.get_api_details_url(object_to_patch)).data

        data_modified = copy.deepcopy(data)
        data_modified[self.field_to_patch['field']] = self.field_to_patch['value']
        del data_modified[self.field_to_patch['exclude']]

        resp = self.client.patch(self.get_api_details_url(object_to_patch),
                                 json.dumps(data_modified, cls=DjangoJSONEncoder),
                                 content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # Make sure that the object was properly saved in the database.
        db_obj = self.all_user_objects.get(**{self.lookup_field: data[self.lookup_field]})
        self.compare_db_obj_with_api(db_obj, resp.data)

        # Restore the object to the DB.
        resp = self.client.patch(self.get_api_details_url(object_to_patch),
                                 json.dumps(data, cls=DjangoJSONEncoder),
                                 content_type='application/json')
        self.assertEqual(resp.status_code, 200)

    @should_check_action(actions_tested=('update',))
    def test_put_bulk_objects(self):
        '''
        Tests that we can edit (PUT) objects in bulk via the API.
        '''
        if 'put' not in self.bulk_actions:
            return

        if not self.field_to_patch:
            return

        objects_to_patch = self.all_user_objects[:3]
        data_list, data_modified_list = [], []
        for object_to_patch in objects_to_patch:
            data = self.client.get(self.get_api_details_url(object_to_patch)).data
            data_list.append(data)

            data_modified = copy.deepcopy(data)
            data_modified[self.field_to_patch['field']] = self.field_to_patch['value']
            data_modified_list.append(data_modified)

        resp = self.client.put(self.api_list_url,
                                 json.dumps(data_modified_list, cls=DjangoJSONEncoder),
                                 content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        for data_modified in data_modified_list:
            # Make sure that the object was properly saved in the database.
            db_obj = self.all_user_objects.get(**{self.lookup_field: data_modified[self.lookup_field]})
            self.compare_db_obj_with_api(db_obj, data_modified)

        for idx, object_to_patch in enumerate(objects_to_patch):
            data = data_list[idx]
            # Restore the object to the DB.
            resp = self.client.patch(self.get_api_details_url(object_to_patch),
                                     json.dumps(data, cls=DjangoJSONEncoder),
                                     content_type='application/json')
            self.assertEqual(resp.status_code, 200)

    @should_check_action(actions_tested=('update',))
    def test_patch_bulk_objects(self):
        '''
        Tests that we can edit (PATCH) objects in bulk via the API.
        '''
        # import pdb;pdb.set_trace()
        if 'patch' not in self.bulk_actions:
            return

        if not self.field_to_patch:
            return

        objects_to_patch = self.all_user_objects[:3]
        data_list, data_modified_list = [], []
        for object_to_patch in objects_to_patch:
            data = self.client.get(self.get_api_details_url(object_to_patch)).data
            data_list.append(data)

            data_modified = copy.deepcopy(data)
            data_modified[self.field_to_patch['field']] = self.field_to_patch['value']
            del data_modified[self.field_to_patch['exclude']]
            data_modified_list.append(data_modified)

        resp = self.client.patch(self.api_list_url,
                                 json.dumps(data_modified_list, cls=DjangoJSONEncoder),
                                 content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        for idx, data_modified in enumerate(data_modified_list):
            # Make sure that the object was properly saved in the database.
            db_obj = self.all_user_objects.get(**{self.lookup_field: data_modified[self.lookup_field]})
            data = data_list[idx]
            data.update(data_modified)
            self.compare_db_obj_with_api(db_obj, data)

        for idx, object_to_patch in enumerate(objects_to_patch):
            data = data_list[idx]
            # Restore the object to the DB.
            resp = self.client.patch(self.get_api_details_url(object_to_patch),
                                     json.dumps(data, cls=DjangoJSONEncoder),
                                     content_type='application/json')
            self.assertEqual(resp.status_code, 200)
