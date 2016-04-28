from django.test import TestCase
from django.contrib.auth import get_user_model

from rest_framework.authtoken.models import Token
from rest_framework.authentication import exceptions

from edu_token_auth.authentication import EduTokenAuthentication


class EduTokenAuthTests(TestCase):
    """
    Adds a test that the number of queries for authenticating a user is 1
    and not 2 like in the original TokenAuthentication implementation.
    """

    def setUp(self):

        self.username = 'john'
        self.email = 'lennon@thebeatles.com'
        self.password = 'password'
        self.member_id = 'member_id'
        self.oxygen_id = 'oxygen_id'
        self.user = get_user_model().objects.create(
            member_id=self.member_id,
            oxygen_id=self.oxygen_id,
            name=self.username, 
            short_name=self.username,
            email=self.email,
        )
        self.user.set_password(self.password)
        self.user.save()

        self.token = Token.objects.get(user=self.user)
        self.key = self.token.key

    def test_post_json_passing_token_auth_makes_one_db_query(self):
        """Ensure EduTokenAuthentication request makes exactly one query to the DB."""

        auth = EduTokenAuthentication()
        func_to_run = lambda: auth.authenticate_credentials(self.key)
        self.assertNumQueries(1, func_to_run)

    def test_invalid_token(self):
        '''
        Test that an invalid token raises the appropriate exception.
        '''

        auth = EduTokenAuthentication()
        token_key = ('1' if self.key[0] != '1' else '2') + self.key[1:]
        self.assertRaises(
            exceptions.AuthenticationFailed,
            auth.authenticate_credentials,
            token_key,
        )

    def test_invalid_user_inactive(self):
        '''
        Test that a token of an inactive user raises the appropriate exception.
        '''

        auth = EduTokenAuthentication()

        user = get_user_model().objects.create(
            member_id=self.member_id + '1',
            oxygen_id=self.oxygen_id + '1',
            name=self.username + '1', 
            short_name=self.username + '1',
            email='a' + self.email,
            is_active=False,
        )
        user.set_password(self.password)
        user.save()

        key = Token.objects.get(user=user).key
        
        self.assertRaises(
            exceptions.AuthenticationFailed,
            auth.authenticate_credentials,
            key,
        )
