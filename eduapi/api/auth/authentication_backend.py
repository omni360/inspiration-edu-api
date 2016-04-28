import requests

from django.contrib.auth import get_user_model
from django.core import exceptions
from django.conf import settings

from .spark_drive_operations import SparkDriveOperations
from .models import IgniteUser

class SparkDriveApiBackend(object):
    '''
    Authenticates a user against the Spark Drive API.

    Receives a session_id and a secure_session_id and checks that the user is
    a Spark Drive API user. If she is, logs the user in and updates the system
    info.

    If not, returns None, as required by Django.    
    '''

    def authenticate(self, session_id=None, secure_session_id=None):

        #no session for spark drive api, meaning not authenticated:
        if not session_id:
            return None

        #initialize Spark Drive operations:
        sparkdrive_operations = SparkDriveOperations(session_id=session_id, secure_session_id=secure_session_id)

        #get (crete if needed) the Ignite user from the logged in member in Spark Drive:
        try:
            user, created = sparkdrive_operations.get_logged_in_ignite_user()
        except sparkdrive_operations.SparkDriveApiError:
            raise exceptions.PermissionDenied

        return user

    def get_user(self, user_id):
        try:
            return get_user_model().objects.get(pk=user_id)
        except get_user_model().DoesNotExist:
            return None
