from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.utils import override_settings
from django.core.urlresolvers import reverse

from rest_framework.test import APITestCase

from notifications.models import Notification

from api.models import Classroom
from api.tasks import notify_user
from api.serializers import NotificationSerializer


@override_settings(
    CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
    CELERY_ALWAYS_EAGER=True,
    BROKER_BACKEND='memory')
class NotificationsTests(TestCase):
    fixtures = ['test_projects_fixture_1.json']

    def test_notification_created_by_notify_task(self):
        recipient = get_user_model().objects.filter(name="Jane Doe")[0]
        actor = get_user_model().objects.filter(name="Ofir Ovadia")[0]
        target_classroom = Classroom.objects.filter(title__icontains='Super Star Destroyer')[0]
        notify_user(recipient=recipient,
                          actor=actor,
                          verb='added to',
                          target=target_classroom,
                          action_object=recipient)
        notifications = Notification.objects.filter(
            recipient=recipient,
            actor_object_id=actor.pk,
            target_object_id=target_classroom.pk,
            action_object_object_id=recipient.pk
        )
        self.assertEquals(notifications.count(), 1, 'More than one notification created.')
        self.assertEquals(notifications[0].unread, True, 'New notification is not marked unread.')


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
        self.user_1 = get_user_model().objects.filter(name__icontains="Jane Doe")[0]
        self.user_2 = get_user_model().objects.filter(name__icontains="Ofir Ovadia")[0]
        self.user_3 = get_user_model().objects.filter(name__icontains="John Doe")[0]
        self.target_classroom = Classroom.objects.filter(title__icontains='Super Star Destroyer')[0]
        notify_user(recipient=self.user_1,
                    actor=self.user_2,
                    verb='added to',
                    target=self.target_classroom,
                    action_object=self.user_1)
        notify_user(recipient=self.user_2,
                    actor=self.user_1,
                    verb='added to',
                    target=self.target_classroom,
                    action_object=self.user_2)
        notify_user(recipient=self.user_3,
                    actor=self.user_2,
                    verb='added to',
                    target=self.target_classroom,
                    action_object=self.user_3)
        self.url_my_notifications = reverse('api:my-notifications')
        # self.url_my_unread_single_notification = reverse('api:my-unread-single-notification',
        #                                                  kwargs={'pk':})
        self.url_my_unread_notifications = reverse('api:my-unread-notifications')
        self.url_my_read_notifications = reverse('api:my-read-notifications')

        self.filters = [
            ({'actorModel__in': 'igniteuser,project'}, {'actor_content_type__model__in': ['igniteuser', 'project']}),
            ({'actorId': self.user_2.id}, {'actor_object_id': self.user_2.id}),
            ({'targetModel__in': 'project,classroom'}, {'actor_content_type__model__in': ['project', 'classroom']}),
            ({'targetId': self.target_classroom.id}, {'actor_content_type__model': self.target_classroom.id}),
            ({'verb': 'added to'}, {'verb': 'added to'}),
            ({'level__in': 'info,error'}, {'level__in': ['info', 'error']}),
            ({'unread': '1'}, {'unread': True}),
        ]

    def test_get_unread_notifications(self):
        self.client.force_authenticate(self.user_1)
        resp = self.client.get(self.url_my_notifications)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data.get('count'), 1)

    def test_mark_as_read_single_notification(self):
        self.client.force_authenticate(self.user_1)
        resp = self.client.get(self.url_my_notifications)
        self.assertEqual(resp.status_code, 200)

        notification_id = resp.data.get('results')[0].get('id')
        url_my_mark_read_single_notification = reverse('api:my-unread-single-notification',
                                                         kwargs={'pk': notification_id })
        resp = self.client.put(url_my_mark_read_single_notification)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Notification.objects.get(id=notification_id).unread, False)

    def test_mark_as_read_all_notifications(self):
        self.client.force_authenticate(self.user_1)
        resp = self.client.get(self.url_my_notifications)
        self.assertEqual(resp.status_code, 200)
        notification_id = resp.data.get('results')[0].get('id')

        resp = self.client.put(self.url_my_unread_notifications)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Notification.objects.get(id=notification_id).unread, False)

    def test_mark_as_unread_single_notification(self):
        notification = Notification.objects.filter(recipient=self.user_1)[0]
        notification.unread = False
        notification.save()

        self.client.force_authenticate(self.user_1)
        url_my_mark_unread_single_notification = reverse('api:my-reread-single-notification',
                                                        kwargs={'pk': notification.id })
        resp = self.client.put(url_my_mark_unread_single_notification)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Notification.objects.get(id=notification.id).unread, True)


    def test_mark_as_unread_all_notification(self):
        notification = Notification.objects.filter(recipient=self.user_1)[0]
        notification.unread = False
        notification.save()

        self.client.force_authenticate(self.user_1)
        resp = self.client.put(self.url_my_read_notifications)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Notification.objects.get(id=notification.id).unread, True)

    def test_notification_filters(self):
        self.client.force_authenticate(self.user_1)

        for api_filters, db_filters in self.filters:

            objs_from_db = Notification.objects.filter(recipient=self.user_1).active()

            resp = self.client.get(self.url_my_notifications, dict(
                api_filters.items() + {'pageSize': objs_from_db.count()}.items()
            ))

            # Make sure we get the correct number of objects with duration gte to 20
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.data['count'], objs_from_db.count(), msg=str(api_filters))
            self.assertSetEqual(set([x['id'] for x in resp.data['results']]), set([x.id for x in objs_from_db]))
