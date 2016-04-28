import json
import unittest

from django.core.urlresolvers import reverse
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Count

from ..models import Project


class ClassroomProjectTestsBase(object):
    '''
    Tests the Project\Classroom API.
    '''

    def get_list_with_min_size(self, min_list_size, for_edit=False):
        user_objects = self.all_user_objects_for_edit if for_edit and self.all_user_objects_for_edit else self.all_user_objects
        return user_objects.annotate(**{
            '%s_num' % self.embedded_obj_p: Count(self.embedded_obj_p)
        }).filter(**{
            '%s_num__gte' % self.embedded_obj_p: min_list_size
        })

    @unittest.skip('Not implemented')
    def test_invalid_data_in_post(self):
        pass

    def test_embed_list_in_object(self):
        """
        Make sure that it's possible to embed the list in the object response.
        """

        obj_id = self.get_list_with_min_size(1)[0].id

        # Make sure that this object has a list attached to it.
        resp = self.client.get(reverse(self.api_details_url, kwargs={'pk': obj_id}), {'embed': ','.join([self.embedded_list_ids])})
        self.assertGreater(len(resp.data[self.embedded_list_ids]), 0)

        # Make sure the list is of ids integers:
        for obj in resp.data[self.embedded_list_ids]:
            self.assertIsInstance(obj, int)

        # Get the object with the embedded list
        resp = self.client.get(reverse(
            self.api_details_url, kwargs={'pk': obj_id}
        ) + '?embed=%s' % self.embedded_obj_p)
        self.assertGreater(len(resp.data[self.embedded_obj_p]), 0)

        # Make sure the list is now embedded
        for obj in resp.data[self.embedded_obj_p]:
            self.assertIn('id', obj)

    def test_add_object_to_embedded_list(self):
        '''
        Make sure its possible to add a new object to a the list.

        That is an object that wasn't in the list until now.
        '''

        # Get a list with at least 2 items.
        obj = self.get_list_with_min_size(2, for_edit=True)[0]

        # Get an ID of an object that's not in the list.
        obj_id = self.embedded_model.objects.exclude(
            id__in=getattr(
                obj, self.embedded_obj_p
            ).all().values_list('id', flat=True)
        ).filter(publish_mode=Project.PUBLISH_MODE_PUBLISHED)[0].id

        resp = self.client.get(
            reverse(self.api_details_url, kwargs={'pk': obj.id}), 
            {'embed': ','.join([self.embedded_list_ids, self.embedded_obj_p])}
        )

        list_ids = resp.data[self.embedded_list_ids]

        self.assertNotIn(obj_id, list_ids)

        # Insert the object to the middle of the list.
        list_ids.insert(int(len(list_ids) / 2), obj_id)

        resp1 = self.client.put(
            resp.data['self'] + '?embed=%s' % ','.join([self.embedded_list_ids, self.embedded_obj_p]),
            json.dumps(resp.data, cls=DjangoJSONEncoder),
            content_type='application/json',
        )

        self.assertIn(resp1.status_code, range(200, 205))

        # Make sure that the object was added and that the response reflects that.
        self.assertIn(obj_id, resp1.data[self.embedded_list_ids])
        self.assertEqual(list_ids, resp1.data[self.embedded_list_ids])
        for idx, obj_id in enumerate(list_ids):
            self.assertEqual(obj_id, resp1.data[self.embedded_obj_p][idx]['id'])

        # Make sure that the object was added in the database
        list_ids_in_db = self.embedded_through_model.objects.filter(**{
            self.model._meta.model_name: obj
        }).order_by('order').values_list('%s_id' % self.embedded_obj_s, flat=True)
        for idx, obj_id in enumerate(list_ids_in_db):
            self.assertEqual(obj_id, resp1.data[self.embedded_list_ids][idx])

    def test_change_embedded_list_order(self):
        '''
        Change the order of a list in an object when using the ?embed= parameter
        '''

        ids_list_name = self.embedded_list_ids

        # Get a list of 2 or more.
        obj_id = self.get_list_with_min_size(2, for_edit=True)[0].id

        resp = self.client.get(reverse(
            self.api_details_url, kwargs={'pk': obj_id}), 
            {'embed': ','.join([self.embedded_list_ids, self.embedded_obj_p])}
        )
        self.assertGreater(len(resp.data[self.embedded_obj_p]), 1)

        api_obj = resp.data

        # Swap the last and first items in the list
        ids_list = api_obj[ids_list_name]
        ids_list[0], ids_list[-1] = ids_list[-1], ids_list[0]

        resp = self.client.put(
            api_obj['self'] + '?embed=%s' % ','.join([self.embedded_list_ids, self.embedded_obj_p]),
            json.dumps(api_obj, cls=DjangoJSONEncoder),
            content_type='application/json'
        )

        self.assertIn(resp.status_code, range(200, 205))

        # Check the IDs list
        self.assertEqual(len(api_obj[ids_list_name]), len(resp.data[ids_list_name]))
        for idx, embedded_obj_id in enumerate(resp.data[ids_list_name]):

            self.assertEqual(embedded_obj_id, api_obj[ids_list_name][idx])

            # Check that objects' order has changed
            self.assertEqual(embedded_obj_id, resp.data[self.embedded_obj_p][idx]['id'])

        # Check that another GET operation returns the new order
        resp2 = self.client.get(reverse(
            self.api_details_url, kwargs={'pk': obj_id}), 
            {'embed': ','.join([self.embedded_list_ids, self.embedded_obj_p])}
        )
        self.assertGreater(len(resp2.data[self.embedded_obj_p]), 0)
        self.assertEqual(resp.data[ids_list_name], resp2.data[ids_list_name])
        self.assertEqual(resp.data[self.embedded_obj_p], resp2.data[self.embedded_obj_p])


    def test_change_list_order_in_object(self):
        '''
        Change the order of the list in an object when NOT using the ?embed=
        parameter.
        '''

        # Get a list longer than 1.
        obj_id = self.get_list_with_min_size(2, for_edit=True)[0].id

        resp = self.client.get(reverse(self.api_details_url, kwargs={'pk': obj_id}), {'embed': ','.join([self.embedded_list_ids])})
        self.assertGreater(len(resp.data[self.embedded_list_ids]), 0)

        api_obj = resp.data

        # Swap the last and first objects in the list
        ids_list_name = self.embedded_list_ids
        ids_list = api_obj[ids_list_name]
        ids_list[0], ids_list[-1] = ids_list[-1], ids_list[0]

        resp2 = self.client.put(
            api_obj['self'] + '?embed=%s' % ','.join([self.embedded_list_ids]),
            json.dumps(api_obj, cls=DjangoJSONEncoder),
            content_type='application/json'
        )

        self.assertIn(resp2.status_code, range(200, 205))

        # Check the list of IDs
        self.assertEqual(len(api_obj[ids_list_name]), len(resp2.data[ids_list_name]))
        for idx, embedded_obj_id in enumerate(resp2.data[ids_list_name]):

            self.assertEqual(embedded_obj_id, api_obj[ids_list_name][idx])

            # Check that objects' order has changed
            self.assertEqual(embedded_obj_id, resp2.data[self.embedded_list_ids][idx])

        # Check that another GET operation returns the new order
        resp3 = self.client.get(reverse(self.api_details_url, kwargs={'pk': obj_id}), {'embed': ','.join([self.embedded_list_ids])})
        self.assertGreater(len(resp3.data[self.embedded_list_ids]), 0)
        self.assertEqual(resp2.data[ids_list_name], resp3.data[ids_list_name])
        self.assertEqual(resp2.data[self.embedded_list_ids], resp3.data[self.embedded_list_ids])

    def test_remove_object_from_list(self):
        '''Test removing an object from the embedded list'''

        ids_list_name = self.embedded_list_ids

        # Get a object with at least 3 lessons.
        obj = self.get_list_with_min_size(3, for_edit=True)[0]

        resp = self.client.get(reverse(self.api_details_url, kwargs={'pk': obj.id}), {'embed': ','.join([self.embedded_list_ids])})

        # Remove an object from the middle of the list.
        removed_obj_id = resp.data[ids_list_name][
            int(len(getattr(obj, self.embedded_obj_p).all()) / 2)
        ]
        resp.data[ids_list_name].remove(removed_obj_id)

        resp1 = self.client.put(
            resp.data['self'] + '?embed=%s' % ','.join([self.embedded_list_ids]),
            json.dumps(resp.data, cls=DjangoJSONEncoder),
            content_type='application/json'
        )

        self.assertIn(resp1.status_code, range(200, 205))

        # Make sure that the object was removed and that the response reflects that.
        self.assertNotIn(removed_obj_id, resp1.data[ids_list_name])
        self.assertEqual(resp.data[ids_list_name], resp1.data[ids_list_name])
        for idx, obj_id in enumerate(resp.data[ids_list_name]):
            self.assertEqual(obj_id, resp1.data[self.embedded_list_ids][idx])

        # Make sure that the object was removed from the database
        objects_ids_in_db = self.embedded_through_model.objects.filter(**{
            self.model._meta.model_name: obj
        }).order_by('order').values_list('%s_id' % self.embedded_obj_s, flat=True)
        for idx, obj_id in enumerate(objects_ids_in_db):
            self.assertEqual(obj_id, resp.data[ids_list_name][idx])

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
