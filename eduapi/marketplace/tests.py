import mock
import unittest
import httpretty

from django.test import TestCase, override_settings
from django.conf import settings
from django.core.urlresolvers import reverse
from django.contrib.auth import get_user_model

from rest_framework.test import APITestCase as DRFTestCase

from api.tests.base_test_case import BaseTestCase
from api.tests.utils.mock_spark_drive_api import MockSparkDriveApi
from marketplace.models import Purchase
from marketplace.views import MarketplaceCallbacks


@override_settings(
    DISABLE_SENDING_CELERY_EMAILS=True,
    ARDUINO_PURCHASE_IDS=['arduino-purchase-1', 'arduino-purchase-2'],
    ARDUINO_PROJECTS_IDS=[1,2,3,4,5],
    MKP_SECRET_TOKEN='123412341234123412341234',
)
class MarketplaceTests(BaseTestCase, DRFTestCase):
    """Tests the Marketplace APIs"""

    fixtures = ['test_projects_fixture_1.json']

    @httpretty.activate
    def test_mkp_purchase_callback(self):
        '''Mkp can callback us with purchase'''

        for i, arduino_purchase_id in enumerate(settings.ARDUINO_PURCHASE_IDS):

            session_id = '281500AC-08A4-477E-9705-2CC024D80869'
            secure_session_id = '21EFBFE7B31CC2E152EE7CB18A0B54D6'

            member_data = {
                'member_id': 'arduino-100-' + str(i),
                'email': 'o@o.com',
                'name': 'Ofir Ovadia',
                'short_name': 'Ofir',
                'avatar': 'http://placekitten.com/300/300/',
                'age': 28,
                'oxygen_id': 'zhNHUV9CJHL2Ryaw' + str(i),
            }
            MockSparkDriveApi.mock_spark_drive_member(member_data)

            resp = self.client.post(reverse('api:mkp-purchase'), {
                'sessionId': '0192383905832',
                'secureSessionId': 'kjahsdfsaoi-woiruweor-12312312',
                'purchasedItemId': arduino_purchase_id,
                'mkpSecretToken': '123412341234123412341234',
            })

            self.assertEqual(resp.status_code, 200)
            self.assertListEqual(
                list(get_user_model().objects.get(
                    member_id=member_data['member_id']
                ).purchases.all().values_list('project_id', flat=True)),
                list(settings.ARDUINO_PROJECTS_IDS),
            )

    def test_mkp_purchase_callback_invalid_purchased_item(self):
        '''Mkp can callback us with purchase'''

        resp = self.client.post(reverse('api:mkp-purchase'), {
            'sessionId': '0192383905832',
            'secureSessionId': 'kjahsdfsaoi-woiruweor-12312312',
            'purchasedItemId': settings.ARDUINO_PURCHASE_IDS[0] + '5555',
            'mkpSecretToken': '123412341234123412341234',
        })

        self.assertEqual(resp.status_code, 400)
        self.assertIn('purchasedItemId', resp.data)


    def test_mkp_purchase_callback_invalid_mkp_identifier(self):
        '''Mkp can callback us with purchase'''

        resp = self.client.post(reverse('api:mkp-purchase'), {
            'sessionId': '0192383905832',
            'secureSessionId': 'kjahsdfsaoi-woiruweor-12312312',
            'purchasedItemId': settings.ARDUINO_PURCHASE_IDS[0],
            'mkpSecretToken': '12341234123412341234123-'
        })
        self.assertEqual(resp.status_code, 403)

    #TODO: We should define some temporary list of arduino projects, because settings.ARDUINO_PROJECTS_IDS[0] - fails if no env variable is introduced
    def test_mkp_purchase_for_user_with_viewer_permission(self):
        """If user already has view permission, change it to teacher"""

        user = get_user_model().objects.exclude(
            id__in=Purchase.objects.all().values_list('id', flat=True),
        ).filter(
            is_child=False,
        ).first()

        purchase = Purchase(
            user=user,
            project_id=settings.ARDUINO_PROJECTS_IDS[0],
            permission=Purchase.VIEW_PERM
        )
        purchase.save()

        mkp_view = MarketplaceCallbacks()
        mkp_view.serializer_class = mock.Mock()

        my_serializer = mkp_view.serializer_class.return_value
        my_serializer.is_valid.return_value=True
        my_serializer.validated_data = {
            'user': user,
            'purchasedItemId': settings.ARDUINO_PURCHASE_IDS[0],
        }

        request = mock.Mock()

        resp = mkp_view.post(request=request)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            Purchase.objects.get(user=user, project_id=settings.ARDUINO_PROJECTS_IDS[0]).permission,
            Purchase.TEACH_PERM,
        )

        purchase.delete()
