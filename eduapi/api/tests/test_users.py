import re
import unittest

from collections import Counter

from django.db.models import Count, Q
from django.db.utils import IntegrityError
from django.db import transaction
from django.core.urlresolvers import reverse
from django.contrib.auth import get_user_model

from rest_framework.test import APITestCase as DRFTestCase
from rest_framework.authtoken.models import Token

from ..serializers import (
    UserSerializer,
    FullUserSerializer,
)
from ..models import (
    IgniteUser,
    ChildGuardian,
)


class UserTests(DRFTestCase):

    fixtures = ['test_projects_fixture_1.json']

    def setUp(self):

        self.public_fields = UserSerializer.Meta.fields
        self.private_fields = list(Counter(FullUserSerializer.Meta.fields) - Counter(self.public_fields))
        self.all_users = get_user_model().objects.annotate(
            guardians_num=Count('guardians')).filter(Q(is_child=False) | Q(guardians_num__gte=1))
        self.filters_tests = [
            {
                'filters': {},
                'results': self.all_users.filter(name='Ofir Ovadia'),
                'status_code': 400,
            },
            {
                'filters': {'name': 'Ofir Ovadia'},
                'results': self.all_users.filter(name='Ofir Ovadia'),
            },
            {
                'filters': {'name__icontains': 'ofi'},
                'results': self.all_users.filter(name__icontains='ofi'),
                'status_code': 400,
            },
            {
                'filters': {'name__contains': 'Ofi'},
                'results': self.all_users.filter(name__contains='Ofi'),
                'status_code': 400,
            },
            {
                'filters': {'name__icontains': 'oFIr'},
                'results': self.all_users.filter(name__icontains='oFIr'),
            },
            {
                'filters': {'name__contains': 'Ofir'},
                'results': self.all_users.filter(name__contains='Ofir'),
            },
            {
                'filters': {'name__exact': 'Ofir Ovadia'},
                'results': self.all_users.filter(name__exact='Ofir Ovadia'),
            },
            {
                'filters': {'name__exact': 'ofir ovadia'},
                'results': self.all_users.filter(name__exact='ofir ovadia'),
            },
            {
                'filters': {'name__iexact': 'ofiR oVAdia'},
                'results': self.all_users.filter(name__iexact='ofir OVADIA'),
            }
        ]


    @classmethod
    def to_snake_case(cls, name):

        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


    # Users List
    # ##########

    def test_can_search_user_list_if_authenticated(self):
        '''Check that every user can get a list of all of the users'''

        all_users = self.all_users
        all_users_ids = [u.id for u in all_users]

        for user in all_users:
            self.client.force_authenticate(user)

            resp = self.client.get(
                reverse('api:user-list') + 
                '?pageSize=' + str(len(all_users)) + 
                '&name=' + all_users[0].name
            )

            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.data['count'], 1)

            for api_user in resp.data['results']:
                self.assertIn(api_user['id'], all_users_ids)

    def test_cant_get_user_list_if_not_authenticated(self):
        '''Check that not authenticated users can't get a list of all users'''

        self.client.force_authenticate(None)
        resp = self.client.get(reverse('api:user-list'))

        self.assertEqual(resp.status_code, 401)

    def test_can_filter_users(self):
        '''Check that filters on users list work'''

        self.client.force_authenticate(get_user_model().objects.all().first())

        for filters in self.filters_tests:
            resp = self.client.get(reverse('api:user-list'), dict(
                filters['filters'].items() + {'pageSize': len(filters['results'])}.items()
            ))

            self.assertEqual(resp.status_code, filters.get('status_code', 200), msg=filters)
            if filters.get('status_code', 200) == 200:
                self.assertEqual(resp.data['count'], len(filters['results']))

                users_ids = [u.id for u in filters['results']]
                for api_user in resp.data['results']:
                    self.assertIn(api_user['id'], users_ids)

    def test_cant_get_unapproved_child_using_filters(self):
        '''Even when filtering, can't get a child which is not approved'''

        self.client.force_authenticate(self.all_users.first())
        
        unapproved_children = get_user_model().objects.filter(is_child=True, is_approved=False)
        self.assertGreaterEqual(len(unapproved_children), 1)

        for child in unapproved_children:

            resp = self.client.get(reverse('api:user-list'), dict({
                'name': child.name,
                'pageSize': get_user_model().objects.all().count()
            }.items()))

            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.data['count'], 0)
            self.assertEqual(len(resp.data['results']), 0)

    def test_can_get_approved_child(self):
        '''Make sure that approved children are reachable via User List API'''

        self.client.force_authenticate(self.all_users.first())
        
        approved_children = get_user_model().objects.filter(is_child=True, is_approved=True)
        self.assertGreaterEqual(len(approved_children), 1)

        for child in approved_children:
            resp = self.client.get(reverse('api:user-list'), dict({
                'pageSize': get_user_model().objects.all().count(),
                'name': child.name,
            }.items()))

            self.assertEqual(resp.status_code, 200)
            self.assertEqual(child.id, resp.data['results'][0]['id'])

    # Users Details
    # #############

    def test_can_get_every_users_details(self):
        
        users = IgniteUser.objects.all()

        for user in users:

            resp = self.client.get(reverse('api:user-detail', kwargs={'pk': user.pk}))

            self.assertEqual(resp.status_code, 200)

            for field_name in self.public_fields:
                db_value = getattr(user, self.to_snake_case(field_name), None)
                if db_value:
                    self.assertEqual(resp.data[field_name], db_value)

    def test_cant_see_users_private_fields(self):
        
        users = IgniteUser.objects.all()

        for user in users:

            resp = self.client.get(reverse('api:user-detail', kwargs={'pk': user.pk}))

            self.assertEqual(resp.status_code, 200)

            for field_name in self.private_fields:
                self.assertNotIn(field_name, resp.data)

    # POST/PUT/PATCH
    # ##############

    def test_cant_post_to_user_list(self):

        user = IgniteUser.objects.all()[0]
        self.client.force_authenticate(user)

        resp = self.client.post(reverse('api:user-list'), {})

        self.assertEqual(resp.status_code, 405)

    def test_cant_post_user(self):

        user = IgniteUser.objects.all()[0]

        resp = self.client.post(reverse('api:user-detail', kwargs={'pk': user.pk}), {})

        self.assertIn(resp.status_code, [401, 405])

    def test_cant_put_user(self):
        user = IgniteUser.objects.all()[0]

        resp = self.client.put(reverse('api:user-detail', kwargs={'pk': user.pk}), {})

        self.assertIn(resp.status_code, [401, 405])

    def test_cant_patch_user(self):
        user = IgniteUser.objects.all()[0]

        resp = self.client.patch(reverse('api:user-detail', kwargs={'pk': user.pk}), {})

        self.assertIn(resp.status_code, [401, 405])

    # DELETE
    # ######

    def test_cant_delete_user_if_not_logged_in(self):
        '''
        DELETE /users/:id/ requires authentication.
        '''

        user = IgniteUser.objects.all()[0]
        self.client.force_authenticate(None)

        resp = self.client.delete(reverse('api:user-detail', kwargs={'pk': user.pk}), {})

        self.assertEqual(resp.status_code, 401)

    def test_cant_delete_user_unless_self_or_guardians(self):
        '''
        DELETE /users/:id/ requires the logged in user to be the 
        deleted user or her guardians.
        '''

        users = IgniteUser.objects.all()
        user = users[0]

        me = next(
            u 
            for u 
            in users 
            if (u.id != user.id and u.id != (user.guardians.all().values_list('id',flat=True)))
        )
        self.client.force_authenticate(me)

        resp = self.client.delete(reverse('api:user-detail', kwargs={'pk': user.pk}), {})

        self.assertEqual(resp.status_code, 403)

    def create_user_and_dependencies(self):
        '''
        Helper function that creates a new user and all of her dependencies:
        Reviews, Children, Guardian, Projects, Lessons, ProjectState, LessonState, 
        Log Entries, Token.

        The reason we create a new user is that we don't want to delete a user 
        from the database.

        The reason we create all of the dependencies is that we want to check
        how they are handled once the user is deleted.
        '''

        u = IgniteUser(
            short_name='Johnny',
            name='John Doe',
            member_id='1234qwe4234234',
            email='j@j.com',
            description='Grade 1 teacher',
            avatar='http://placekitten.com/150/150/',
            oxygen_id='ye7382972',
        )
        u.save()
        ChildGuardian(child=u, guardian=IgniteUser.objects.first()).save()

        child = IgniteUser(
            short_name='Kiddo',
            name='John Kid',
            member_id='12341111qwe4234234',
            email='j@jkid.com',
            avatar='http://placekitten.com/150/150/',
            is_child=True,
            is_approved=True,
            oxygen_id='ertujslajweoiralgpwrl;',
        )
        child.save()
        ChildGuardian(child=child, guardian=u).save()
        t = Token.objects.get_or_create(user=u)

        # Create dependencies.
        managers = u._meta.get_all_related_objects()
        managers = [(m.field.name, getattr(u, m.get_accessor_name())) for m in managers]
        managers = [(a, m) for a, m in managers if hasattr(m, 'create') and not m.exists()]
        for attr, mgr in managers:
            # Create an object by cloning an existing object and saving with the
            # user and a None PK.
            len_before = mgr.model.objects.all().count()
            obj = mgr.model.objects.first()
            if obj:
                obj.pk = None
                setattr(obj, attr, u)
                try:
                    with transaction.atomic():  #use atomic transaction in case the query will fail
                        obj.save()
                except IntegrityError:  #catch duplicate unique values and continue
                    continue
                # Make sure that creation succeeded by comparing the length of all
                # objects after the creation to the length before.
                self.assertEqual(mgr.model.objects.all().count(), len_before + 1)

        return u

    def delete_user_and_check_response(self, u):
        '''
        Helper function that deletes a user 'u' and checks that the dependencies
        were handled correctly. Namely, that the guardian wasn't deleted and that
        dependent objects (reviews written by user, ProjectStates for projects
        taken by user, etc.) were deleted.
        '''

        self_url = reverse('api:user-detail', kwargs={'pk': u.pk})
        resp = self.client.get(self_url)

        self.assertEqual(resp.status_code, 200)
        self.assertIn(self_url, resp.data['self'])

        resp2 = self.client.delete(self_url)
        self.assertEqual(resp2.status_code, 204)
        self.assertFalse(IgniteUser.objects.filter(id=u.id).exists())

        # Make sure that children are deleted
        self.assertFalse(IgniteUser.objects.filter(id__in=[w.id for w in u.children.all()]).exists())

        # Make sure that the guardian wasn't deleted
        for g in u.guardians.all():
            self.assertTrue(IgniteUser.objects.filter(id=g.id).exists())

        # Make sure that all of the objects that need to be deleted are deleted.
        managers = u._meta.get_all_related_objects() + u._meta.get_all_related_many_to_many_objects()
        managers = [getattr(u, m.get_accessor_name()) for m in managers]
        managers = [m for m in managers if hasattr(m, 'exists')]
        for mgr in managers:
            self.assertFalse(mgr.exists())

    def test_cant_delete_self(self):
        '''
        A user can NOT DELETE herself.
        '''

        u = self.create_user_and_dependencies()
        self.client.force_authenticate(u)

        self_url = reverse('api:user-detail', kwargs={'pk': u.pk})
        resp = self.client.get(self_url)

        self.assertEqual(resp.status_code, 200)
        self.assertIn(self_url, resp.data['self'])

        resp2 = self.client.delete(self_url)
        self.assertEqual(resp2.status_code, 403)

    def test_can_delete_child(self):
        '''
        A user can DELETE her children.
        '''

        u = self.create_user_and_dependencies()
        self.client.force_authenticate(u.guardians.all().first())
        self.delete_user_and_check_response(u)



