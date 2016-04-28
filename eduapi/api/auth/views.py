from django.contrib.auth import get_user_model
import requests
import urllib
from urlparse import urlparse

from django.http import HttpResponseRedirect
from django.conf import settings
from django.utils.timezone import now as utc_now

from rest_framework import serializers, generics, status
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from api.views import GuardianOrReadOnly

from oxygen_operations import OxygenOperations, _OxygenRequestFailed

from utils_app.sanitize import sanitize_string
from .spark_drive_operations import SparkDriveOperations
from .serializers import AuthTokenSerializer, PasswordResetSerializer

from api.tasks import sync_logged_in_user


class ObtainApiAuthToken(ObtainAuthToken):
    '''
    The same as DRF's ObtainAuthToken, but uses our own AuthTokenSerializer
    instead of DRF's.
    '''

    serializer_class = AuthTokenSerializer

    def get(self, request, redirect):


        # If we're not in a debug environment, make sure that the redirect URL
        # matches the FE's home URL. Otherwise raise an error.
        if  not settings.DEBUG:
            parsed_redirect = urlparse(redirect)
            parsed_fe_home = urlparse(settings.IGNITE_FRONT_END_BASE_URL)

            # Check that the URL is valid by checking the domain and the protocol.
            if ((parsed_redirect.scheme not in ['http', 'https']) or 
                (parsed_redirect.netloc != parsed_fe_home.netloc)):

                raise serializers.ValidationError('Invalid redirect path after authentication')

        tokenkey = sanitize_string(request.GET.get('tokenkey', ''))

        if not tokenkey:
            return HttpResponseRedirect(redirect + '?' + urllib.urlencode({
                'loginError': 'Failed to complete the log in process. Invalid token received from Log In service.'
            }))

        #initialize spark drive api with no session:
        sparkdrive_operations = SparkDriveOperations()

        #authenticate spark drive api session by token:
        try:
            auth_data = sparkdrive_operations.authenticate_token(tokenkey)
        except SparkDriveOperations.SparkDriveApiError:
            return HttpResponseRedirect(redirect + '?' + urllib.urlencode({
                'loginError': 'Failed to complete the log in process'
            }))

        serializer = self.serializer_class(data={
            'sessionId': sparkdrive_operations.session_id,
            'secureSessionId': sparkdrive_operations.secure_session_id,
        })

        if serializer.is_valid():
            user = serializer.validated_data['user']

            #sync the logged in user data from SparkDrive in background via Celery task:
            sync_logged_in_user.delay(
                user,
                serializer.validated_data['sessionId'],
                serializer.validated_data['secureSessionId']
            )

            # Update last_login time of the user:
            # Note: last_login field is originally altered by admin site login, and we use the same field to save
            #       the last time user logs in through this authentication serializer.
            is_first_login = user.last_login is None
            user.last_login = utc_now()
            user.save(update_fields=['last_login'], change_updated_field=False)

            token, created = Token.objects.get_or_create(user=user)
            redirect_query_params = {
                'sessionId': sparkdrive_operations.session_id,
                'secureSessionId': sparkdrive_operations.secure_session_id,
                'apiToken': token.key,
            }
            #if first login, then add indicator flag to redirect query params:
            if is_first_login:
                redirect_query_params['isFirstLogin'] = 'true'
            return HttpResponseRedirect(redirect + '?' + urllib.urlencode(redirect_query_params))

        return HttpResponseRedirect(redirect + '?' + urllib.urlencode({
            'loginError': 'Failed to complete the log in process'
        }))


class ResetOxygenPassword(generics.GenericAPIView):
    serializer_class = PasswordResetSerializer
    permission_classes = (GuardianOrReadOnly,)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        child = get_user_model().objects.get(id=self.kwargs.get('child_pk'))
        self.check_object_permissions(self.request, child)

        if serializer.is_valid(raise_exception=True):
            oxygen_operations = OxygenOperations(
                session_id=serializer.validated_data['sessionId'],
                secure_session_id=serializer.validated_data['secureSessionId']
            )
            try:
                oxygen_operations.reset_child_password(
                guardian=self.request.user,
                child=child,
                password=serializer.validated_data['password'])
                return Response(status=status.HTTP_200_OK)
            except _OxygenRequestFailed as e:
                return Response(data={'error': e.oxygen_error_desc}, status=status.HTTP_417_EXPECTATION_FAILED)

