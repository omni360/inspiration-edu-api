from django.core.urlresolvers import reverse

from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase as DRFTestCase

class BasicProjectTests(DRFTestCase):
    '''
    Basic tests that don't have anywhere else to go :-(
    '''

    fixtures = ['test_projects_fixture_1.json']

    api_with_authentication = reverse('api:me')

    def test_authorization_header(self):
        '''
        Test that requests with an Authorization header work

        The reason we check this is that usually the tests use 
        force_authenticate in order to log the user in. We want to check
        that our authentication method works for real and not just because
        of a pre-configuration.
        '''

        self.client.force_authenticate(None)
        token = Token.objects.all().first()
        resp = self.client.get(self.api_with_authentication, HTTP_AUTHORIZATION='Token %s' % token.key)

        self.assertEqual(resp.status_code, 200)

    def test_no_authorization_header(self):
        '''
        Test that requests without an Authorization header don't work

        For why we're testing this explicitly, check the doc for 
        test_authorization_header.
        '''

        self.client.force_authenticate(None)
        resp = self.client.get(self.api_with_authentication)

        self.assertEqual(resp.status_code, 401)
