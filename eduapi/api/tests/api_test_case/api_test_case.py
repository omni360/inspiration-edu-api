import re
import types
import inspect

from django.core.urlresolvers import reverse, NoReverseMatch

from .generics import ApiListCreateTestCase, ApiRetrieveUpdateDeleteTestCase


class ApiTestCase(ApiListCreateTestCase, ApiRetrieveUpdateDeleteTestCase):

    longMessage = True

    def setUp(self):

        self.api_test_init()

        self.key = getattr(self, 'sort_key', None)
        self.lookup_field = getattr(self, 'lookup_field', 'id')

        # This is to make us foolproof in case the user used get, post, put...
        # instead of create, list, retrieve...
        temp_actions = getattr(self, 'actions', ('list', 'retrieve','create', 'update', 'patch', 'delete',))
        self.actions = []
        if 'list' in temp_actions or 'get' in temp_actions:
            self.actions.append('list')
            self.actions.append('get')
        if 'retrieve' in temp_actions or 'get' in temp_actions:
            self.actions.append('retrieve')
            self.actions.append('get')
        if 'create' in temp_actions or 'post' in temp_actions:
            self.actions.append('create')
            self.actions.append('post')
        if 'delete' in temp_actions or 'destroy' in temp_actions:
            self.actions.append('delete')
            self.actions.append('destroy')
        if 'update' in temp_actions or 'put' in temp_actions:
            self.actions.append('put')
            self.actions.append('update')
        if 'update' in temp_actions or 'patch' in temp_actions:
            self.actions.append('patch')
            self.actions.append('update')


        self.serializer = getattr(self, 'serializer', None)
        if not getattr(self, 'fields', None):
            self.fields = getattr(getattr(self.serializer, 'Meta', None), 'fields', ())
        self.dropfields = getattr(self, 'dropfields', self.fields)

        if hasattr(self, 'get_all_user_objects'):
            self.all_user_objects = self.get_all_user_objects()
        else:
            self.all_user_objects = getattr(self, 'all_user_objects', None)
        self.all_user_objects_for_edit = getattr(self, 'all_user_objects_for_edit', None)

        self.object_to_delete = getattr(self, 'object_to_delete', None)
        self.all_public_objects = getattr(self, 'all_public_objects', None)
        self.filters = getattr(self, 'filters', [])
        self.pagination = getattr(self, 'pagination', False)
        self.free_text_fields = getattr(self, 'free_text_fields', [])
        self.allow_subset_of_fields = getattr(self, 'allow_subset_of_fields', True)
        self.with_choices_on_get = getattr(self, 'with_choices_on_get', True)
        
        self.api_list_url = getattr(self, 'api_list_url', None)
        self.api_details_url = getattr(self, 'api_details_url', None)
        self.object_to_post = getattr(self, 'object_to_post', None)
        self.field_to_put = getattr(self, 'field_to_put', None)
        self.field_to_patch = getattr(self, 'field_to_patch', None)
        self.non_existant_obj_details_url = getattr(self, 'non_existant_obj_details_url', None)
        self.global_user = getattr(self, 'global_user', [None])[0]
        self.allow_unauthenticated_get = getattr(self, 'allow_unauthenticated_get', True)

        self.bulk_actions = getattr(self, 'bulk_actions', [])
        self.put_actions = getattr(self, 'put_actions', [])

        self.check_fields = getattr(self, 'check_fields', [])  #in the format of: (field_name, is_successful, field_input, field_output(optional when successful))

        self.client.force_authenticate(user=self.global_user)

    def api_test_init(self):
        pass

    @classmethod
    def to_camel_case(cls, snake_str):

        components = snake_str.split('_')
        # We capitalize the first letter of each component except the first one
        # with the 'title' method and join them together.
        return components[0] + "".join(x.title() for x in components[1:])
    
    @classmethod
    def to_snake_case(cls, name):

        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

    def compare_db_obj_with_api(self, db_obj, api_obj, msg=None):

        primitive_types = (
            types.NoneType,
            types.BooleanType,
            types.IntType,
            types.LongType,
            types.FloatType,
            types.ComplexType,
            types.StringType,
            types.UnicodeType,
            types.TupleType,
            types.ListType,
            types.DictType,
        )

        msg = msg or ''

        for field_name in self.fields:
            if field_name not in self.dropfields:
                db_value = getattr(db_obj, self.to_snake_case(field_name), None)

                if db_value and isinstance(db_value, primitive_types):
                    if isinstance(db_value, int) or isinstance(primitive_types, int):
                        self.assertEqual(int(api_obj[field_name]), int(db_value), msg=msg + ', field_name: %s' % field_name)
                    else:
                        self.assertEqual(api_obj[field_name], db_value, msg=msg + ', field_name: %s' % field_name)

    def compare_db_obj_list_with_api(self, db_objs, api_results):

        sort_key = lambda x: getattr(x, self.key, None) or (hasattr(x, 'get') and x.get(self.key))

        db_objs = sorted(db_objs, key=sort_key)
        api_objs = sorted(api_results, key=sort_key)

        # Make sure that the number of objects in the response matches 
        self.assertEqual(len(api_objs), len(db_objs))

        # Make sure that all of the objects in the database are in the response
        for idx, db_obj in enumerate(db_objs):

            self.compare_db_obj_with_api(db_obj, api_objs[idx])

    def get_api_details_url(self, obj):
        obj_lookup = getattr(obj, self.lookup_field)
        try:
            return reverse(self.api_details_url, kwargs={'pk': obj_lookup})
        except NoReverseMatch:
            # In case the url was already parsed, replace the placeholder
            # '0' pk with the real one. It's also possible that no replacement
            # is needed, in which case the original url is returned.
            return self.api_details_url.replace('0', str(obj_lookup))

    def test_api_methods_not_allowed(self):
        '''Tests that any not supported actions return 405 method not allowed.'''
        api_list_url = self.api_list_url
        api_details_url = self.get_api_details_url(self.all_user_objects[0]) if len(self.all_user_objects) else None

        not_allowed_methods = {'list', 'retrieve','create', 'update', 'patch', 'delete',} - set(self.actions)
        for method in not_allowed_methods:
            if api_list_url:
                if method == 'list':
                    resp = self.client.get(api_list_url)
                elif method == 'create':
                    resp = self.client.post(api_list_url, {})
            elif api_details_url:
                if method == 'retrieve':
                    resp = self.client.get(api_details_url)
                elif method == 'update':
                    resp = self.client.put(api_details_url, {})
                elif method == 'patch':
                    resp = self.client.patch(api_details_url, {})
                elif method == 'delete':
                    resp = self.client.delete(api_details_url, {})

            if resp:
                # The method can be restricted by permission, or by allowed view methods
                self.assertIn(resp.status_code, (403, 405))
