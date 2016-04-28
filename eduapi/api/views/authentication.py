import base64
from django_redis import get_redis_connection

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password

from rest_framework import exceptions
from rest_framework import authentication

class RedisAuthentication(authentication.BaseAuthentication):
    '''
    Redis Authentication. 

    Use an hash value from the request's query parameters to log the user in.
    The hash value is mapped to a user in Redis.

    Whoever set the hash value is responsible for the hash's expiry.
    '''

    REDIS_AUTH_PREFIX = 'authhash_'

    @classmethod
    def create_hash(cls, user_id):
        '''
        Converts a user_id into a hash value.

        Uses Django's make_password mechanism to create the hash value.
        Then use base64 URL safe to encode the hash. The idea is that the
        hash will be able to be used in URLs.
        '''
        return base64.urlsafe_b64encode(
            make_password(user_id).rpartition('$')[-1]
        )

    def authenticate(self, request):

        # Get hash from URL kwargs
        redis_hash = request.parser_context['kwargs'].get('hash')
        if not redis_hash:
            return None

        # Get the user ID from the Redis server.
        r = get_redis_connection('default')
        user_id = r.hget(self.REDIS_AUTH_PREFIX + redis_hash, 'user_id')

        if not user_id:
            return None

        try:
            # Get the user object using the user ID
            user = get_user_model().objects.get(id=user_id)
        except get_user_model().DoesNotExist:
            raise exceptions.AuthenticationFailed('No such user')

        return (user, None)

class CacheAuthentication(authentication.BaseAuthentication):
    CACHE_AUTH_PREFIX = 'authhash_'

    @classmethod
    def create_hash(cls, user_id):
        '''
        Converts a user_id into a hash value.

        Uses Django's make_password mechanism to create the hash value.
        Then use base64 URL safe to encode the hash. The idea is that the
        hash will be able to be used in URLs.
        '''
        return base64.urlsafe_b64encode(
            make_password(user_id).rpartition('$')[-1]
        )

    def authenticate(self, request):

        # Get hash from URL kwargs
        a_hash = request.parser_context['kwargs'].get('hash')
        if not a_hash:
            return None

        # Get the user ID from the cache.
        user_id = cache.get(self.CACHE_AUTH_PREFIX + a_hash, 'user_id')

        if not user_id:
            return None

        try:
            # Get the user object using the user ID
            user = get_user_model().objects.get(id=user_id)
        except get_user_model().DoesNotExist:
            raise exceptions.AuthenticationFailed('No such user')

        return (user, None)