from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.test.utils import override_settings
from django.core.urlresolvers import reverse

from rest_framework.test import APITestCase

from notifications.models import Notification

from api.models import Classroom, Project, ViewInvite
from api.tasks import notify_user


@override_settings(
    CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
    CELERY_ALWAYS_EAGER=True,
    BROKER_BACKEND='memory')
class NotificationsApiTests(APITestCase):
    """
    Tests the ProjectState and LessonState API.
    """

    fixtures = ['test_projects_fixture_1.json']

    def setUp(self):
        # Create notifications pull
        self.unpublished_project = Project.objects.filter(publish_mode=Project.PUBLISH_MODE_EDIT)[0]
        self.unpublished_project_hash_url = reverse('api:view-invite-detail',
                                                    kwargs={'project_id': self.unpublished_project.id})
        self.user_not_related_to_project = get_user_model().objects.exclude(
            Q(id=self.unpublished_project.owner.id) |
            Q(id__in=self.unpublished_project.owner.delegates.all()) |
            Q(id__in=self.unpublished_project.owner.guardians.all())
        )[0]

    def test_owner_can_create_hash_for_unpublished_project(self):
        self.client.force_authenticate(self.unpublished_project.owner)

        resp = self.client.post(self.unpublished_project_hash_url)

        self.assertEqual(resp.status_code, 201)
        self.assertTrue(ViewInvite.objects.get(project=self.unpublished_project))

    def test_owner_can_get_created_hash_for_unpublished_project(self):
        # create invite
        self.client.force_authenticate(self.unpublished_project.owner)
        resp1 = self.client.post(self.unpublished_project_hash_url)
        self.assertEqual(resp1.status_code, 201)

        # get hash
        resp2 = self.client.get(self.unpublished_project_hash_url)
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp1.data.get('hash'), resp2.data.get('hash'))

    def test_post_twice_generates_same_hash(self):
        # create invite
        self.client.force_authenticate(self.unpublished_project.owner)
        resp1 = self.client.post(self.unpublished_project_hash_url)
        self.assertEqual(resp1.status_code, 201)

        # re-create invite
        self.client.force_authenticate(self.unpublished_project.owner)
        resp2 = self.client.post(self.unpublished_project_hash_url)
        self.assertEqual(resp2.status_code, 200)

        self.assertEqual(resp1.data['hash'], resp2.data['hash'])

    def test_owner_can_get_delete_hash_for_unpublished_project(self):
        # create invite
        self.client.force_authenticate(self.unpublished_project.owner)
        resp1 = self.client.post(self.unpublished_project_hash_url)
        self.assertEqual(resp1.status_code, 201)

        # delete hash
        resp2 = self.client.delete(self.unpublished_project_hash_url)
        self.assertEqual(resp2.status_code, 204)

    def test_not_owner_is_not_permitted_for_crud_actions(self):
        # try create invite
        self.client.force_authenticate(self.user_not_related_to_project)
        resp1 = self.client.post(self.unpublished_project_hash_url)
        self.assertEqual(resp1.status_code, 403)

        # create invite
        self.client.force_authenticate(self.unpublished_project.owner)
        resp1 = self.client.post(self.unpublished_project_hash_url)
        self.assertEqual(resp1.status_code, 201)

        self.client.force_authenticate(self.user_not_related_to_project)

        # get hash
        resp2 = self.client.get(self.unpublished_project_hash_url)
        self.assertEqual(resp2.status_code, 403)

        # delete hash
        resp3 = self.client.delete(self.unpublished_project_hash_url)
        self.assertEqual(resp3.status_code, 403)

    def test_invited_user_can_view_unpublished_project_using_hash(self):
        # create invite
        self.client.force_authenticate(self.unpublished_project.owner)
        resp = self.client.post(self.unpublished_project_hash_url)
        self.assertEqual(resp.status_code, 201)
        hash = resp.data.get('hash')

        # login not related user
        self.client.force_authenticate(self.user_not_related_to_project)

        # Try to get project without hash and fail
        project_resp = self.client.get(
            reverse(
                'api:project-detail',
                kwargs={'pk': self.unpublished_project.id}))
        self.assertEqual(project_resp.status_code, 404) #we handle unpublished project as not existing

        # Try to get project without hash and get it
        project_resp = self.client.get(
            reverse(
                'api:project-detail',
                kwargs={'pk': self.unpublished_project.id}),
            {'hash': resp.data.get('hash')})
        self.assertEqual(project_resp.status_code, 200)

    def test_invited_user_can_view_unpublished_project_lessons_using_hash(self):
        # create invite
        self.client.force_authenticate(self.unpublished_project.owner)
        resp = self.client.post(self.unpublished_project_hash_url)
        self.assertEqual(resp.status_code, 201)
        hash = resp.data.get('hash')

        # login not related user
        self.client.force_authenticate(self.user_not_related_to_project)

        # Try to get project without hash and fail
        project_resp = self.client.get(
            reverse(
                'api:project-detail',
                kwargs={'pk': self.unpublished_project.id}))
        self.assertEqual(project_resp.status_code, 404) #we handle unpublished project as not existing

        # Try to get project without hash and get it
        project_resp = self.client.get(
            reverse(
                'api:project-lesson-list',
                kwargs={'project_pk': self.unpublished_project.id}),
            {'hash': resp.data.get('hash')})
        self.assertEqual(project_resp.status_code, 200)

    def test_invited_user_can_view_unpublished_project_lesson_using_hash(self):
        # create invite
        self.client.force_authenticate(self.unpublished_project.owner)
        resp = self.client.post(self.unpublished_project_hash_url)
        self.assertEqual(resp.status_code, 201)
        hash = resp.data.get('hash')

        # login not related user
        self.client.force_authenticate(self.user_not_related_to_project)

        # Try to get project without hash and fail
        project_resp = self.client.get(
            reverse(
                'api:project-detail',
                kwargs={'pk': self.unpublished_project.id}))
        self.assertEqual(project_resp.status_code, 404) #we handle unpublished project as not existing

        # Try to get project without hash and get it
        project_resp = self.client.get(
            reverse(
                'api:project-lesson-detail',
                kwargs={'project_pk': self.unpublished_project.id,
                        'pk': self.unpublished_project.lessons.annotate(step_count=Count('steps')).filter(step_count__gt=0).first().id
                        }),
            {'hash': resp.data.get('hash'), 'embed': 'steps'})
        self.assertEqual(project_resp.status_code, 200)
        self.assertGreater(len(project_resp.data.get('steps')), 0)


    def test_invited_user_can_view_unpublished_project_lesson_with_steps_using_hash(self):
        # create invite
        self.client.force_authenticate(self.unpublished_project.owner)
        resp = self.client.post(self.unpublished_project_hash_url)
        self.assertEqual(resp.status_code, 201)
        hash = resp.data.get('hash')

        # login not related user
        self.client.force_authenticate(self.user_not_related_to_project)

        # Try to get project without hash and fail
        project_resp = self.client.get(
            reverse(
                'api:project-detail',
                kwargs={'pk': self.unpublished_project.id}))
        self.assertEqual(project_resp.status_code, 404) #we handle unpublished project as not existing

        # Try to get project without hash and get it
        project_resp = self.client.get(
            reverse(
                'api:project-lesson-detail',
                kwargs={'project_pk': self.unpublished_project.id,
                        'pk': self.unpublished_project.lessons.all().first().id
                        }),
            {'hash': hash})
        self.assertEqual(project_resp.status_code, 200)

    def test_invited_anonymous_user_can_view_unpublished_project_using_hash(self):
        # create invite
        self.client.force_authenticate(self.unpublished_project.owner)
        resp = self.client.post(self.unpublished_project_hash_url)
        self.assertEqual(resp.status_code, 201)
        hash = resp.data.get('hash')

        # login not related user
        self.client.force_authenticate(None)

        # Try to get project without hash and fail
        project_resp = self.client.get(
            reverse(
                'api:project-detail',
                kwargs={'pk': self.unpublished_project.id}))
        self.assertEqual(project_resp.status_code, 404) #we handle unpublished project as not existing

        # Try to get project without hash and get it
        project_resp = self.client.get(
            reverse(
                'api:project-detail',
                kwargs={'pk': self.unpublished_project.id}),
            {'hash': resp.data.get('hash')})
        self.assertEqual(project_resp.status_code, 200)