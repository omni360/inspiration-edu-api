import os
import requests
from urlparse import urlparse
import urllib
import binascii
import hashlib

from django.utils.timezone import now as utc_now
from django.conf import settings


class _SparkDriveApiError(Exception):
    '''Exception that Spark Drive API request has failed'''
    spark_status_code = None
    spark_error_code = None
    spark_error_message = None
    spark_error_data = None
    spark_error_error_id = None
    def __init__(self, error_msg='', spark_error=None, spark_status_code=None, *args, **kwargs):
        self.spark_status_code = spark_status_code
        if spark_error:
            self.spark_error_code = spark_error.get('code')
            self.spark_error_message = spark_error.get('message')
            self.spark_error_data = spark_error.get('data')
            self.spark_error_error_id = spark_error.get('error_id')
        if self.spark_error_code is not None:
            spark_error_msg = 'SparkDrive Error (%s)' %(self.spark_error_code,)
            if self.spark_error_message is not None:
                spark_error_msg += ': %s' %(self.spark_error_message,)
            error_msg = error_msg+' ['+spark_error_msg+']' if error_msg else spark_error_msg
        super(_SparkDriveApiError, self).__init__(error_msg, *args, **kwargs)


class SparkDriveApi:

    #settings:
    sparkdrive_base_url = settings.SPARK_DRIVE_API
    sparkdrive_afc = settings.SPARK_AFC
    sparkdrive_api1 = sparkdrive_base_url + '/API/v1'
    sparkdrive_api2 = sparkdrive_base_url + '/api/v2'
    sparkdrive_upload_server = None
    sparkdrive_upload_api = None
    sparkdrive_admin_member_id = settings.SPARK_ADMIN_MEMBER_ID

    #SparkDrive request failed custom exception:
    SparkDriveApiError = _SparkDriveApiError

    def __init__(self, session_id=None, secure_session_id=None):
        self.session_id = session_id
        self.secure_session_id = secure_session_id

    def _parse_sparkdrive_response(self, sparkdrive_response):
        try:
            sparkdrive_response.data = sparkdrive_response.json()
        except ValueError:
            raise self.SparkDriveApiError('Failed to fetch response (invalid json)!', spark_status_code=sparkdrive_response.status_code)

    def _get_request_headers(self, with_session=True, with_secure=False):
        headers = {
            'X-AFC': settings.SPARK_AFC,
        }
        if with_session:
            headers['X-Session'] = self.session_id
            if with_secure:
                headers['X-Secure-Session'] = self.secure_session_id
        return headers

    def authenticate_token(self, token_key):
        #authenticate session by token:
        return self.authenticate_token_v2(token_key)

    def authenticate_token_v1(self, token_key):
        #authenticate session by token (using v1):
        sparkdrive_resp = requests.get(
            self.sparkdrive_base_url + '/TokenAPI/index.cfm',
            params={
                'package': 'Login',
                'op': 'AuthenticateToken',
                'format': 'json',
                'afc': settings.SPARK_AFC,
                'tokenkey': token_key,
                'client_secret': settings.SPARK_CLIENT_SECRET,
                'secure': 1,
                'token': 'wp', # TODO: What's this?
            }
        )
        self._parse_sparkdrive_response(sparkdrive_resp)

        if sparkdrive_resp.status_code in xrange(200, 210):
            auth_resp = sparkdrive_resp.data.get('LOGIN_AUTHENTICATETOKEN_REPLY')
            self.session_id = auth_resp.get('SESSION')
            self.secure_session_id = auth_resp.get('SECURESESSION')
            return auth_resp
        else:
            raise self.SparkDriveApiError('SparkDrive authenticate token.', spark_error=sparkdrive_resp.data, spark_status_code=sparkdrive_resp.status_code)

    def authenticate_token_v2(self, token_key):
        #authenticate session by token (using v2):
        sparkdrive_resp = requests.get(
            self.sparkdrive_api2 + '/login/authenticatetoken',
            params={
                'afc': settings.SPARK_AFC,
                'login_secret': settings.SPARK_CLIENT_SECRET,
                'token_key': token_key,
            }
        )
        self._parse_sparkdrive_response(sparkdrive_resp)

        if sparkdrive_resp.status_code == 200:
            auth_resp = sparkdrive_resp.data
            self.session_id = auth_resp.get('session')
            self.secure_session_id = auth_resp.get('secure_session')
            return auth_resp
        else:
            raise self.SparkDriveApiError('SparkDrive authenticate token v2.', spark_error=sparkdrive_resp.data, spark_status_code=sparkdrive_resp.status_code)

    def member_data(self):
        #get member data of the member identified with the session:
        sparkdrive_resp = requests.get(
            self.sparkdrive_api1 + '/Member',
            headers=self._get_request_headers(),
        )
        self._parse_sparkdrive_response(sparkdrive_resp)

        if sparkdrive_resp.status_code == 200:
            return sparkdrive_resp.data
        else:
            raise self.SparkDriveApiError('SparkDrive member data.', spark_error=sparkdrive_resp.data, spark_status_code=sparkdrive_resp.status_code)

    def member_data_v2(self, member_id=None):
        #get member data by id:
        sparkdrive_resp = requests.get(
            self.sparkdrive_api2 + '/members' + ('/%s' %(member_id,) if member_id else ''),
            headers=self._get_request_headers(),
        )
        self._parse_sparkdrive_response(sparkdrive_resp)

        if sparkdrive_resp.status_code == 200:
            return sparkdrive_resp.data.get('member')
        else:
            raise self.SparkDriveApiError('SparkDrive member data v2.', spark_error=sparkdrive_resp.data, spark_status_code=sparkdrive_resp.status_code)

    def member_data_v2_by_oxygen_id(self, oxygen_id):
        #prepare params:
        oxygen_consumer_key = settings.OXYGEN_CONSUMER_KEY
        ts_datetime = utc_now()
        params = {}
        params['ts'] = ts_datetime.strftime('%Y-%m-%d %H:%M:%S')
        params['afc'] = self.sparkdrive_afc
        params['member_code'] = binascii.hexlify((self.sparkdrive_admin_member_id or '') + '#' + params['ts'])
        params['hash'] = hashlib.sha256(params['afc'] + params['member_code'] + params['ts'] + oxygen_consumer_key).hexdigest()

        #get member data by oxygen id:
        sparkdrive_resp = requests.get(
            self.sparkdrive_api2 + '/admin/members/oxygen/%s?%s' %(oxygen_id, urllib.urlencode(params)),
            headers=self._get_request_headers(),
        )
        self._parse_sparkdrive_response(sparkdrive_resp)

        if sparkdrive_resp.status_code == 200:
            return sparkdrive_resp.data.get('member')
        else:
            raise self.SparkDriveApiError('SparkDrive member data v2 by oxygen ID.', spark_error=sparkdrive_resp.data, spark_status_code=sparkdrive_resp.status_code)

    def get_upload_server(self):
        if not self.sparkdrive_upload_server:
            sparkdrive_resp = requests.get(self.sparkdrive_api2 + '/server/upload')
            self._parse_sparkdrive_response(sparkdrive_resp)
            if sparkdrive_resp.status_code == 200:
                self.sparkdrive_upload_server = sparkdrive_resp.data['server']
                self.sparkdrive_upload_api = 'https://' + self.sparkdrive_upload_server + '/api/v2/files/upload'
            else:
                raise self.SparkDriveApiError('SparkDrive upload server query.', sparkdrive_resp.data, spark_status_code=sparkdrive_resp.status_code)
        return self.sparkdrive_upload_server

    def upload_file_from_url(self, fileurl, filename=None, public=False):
        #if no filename is given, get it from the url string:
        if not filename:
            filename = os.path.basename(urlparse(fileurl).path)

        #upload file to spark drive via url:
        self.get_upload_server()  #fetch spark drive upload server api
        sparkdrive_resp = requests.post(
            self.sparkdrive_upload_api,
            headers=self._get_request_headers(),
            data={
                'fileurl': fileurl,
                'filename': filename,
                'public': 'true' if public else 'false',
            }
        )
        self._parse_sparkdrive_response(sparkdrive_resp)

        if sparkdrive_resp.status_code == 200:
            if len(sparkdrive_resp.data['files']) > 0:
                return sparkdrive_resp.data['files'][0]
            raise self.SparkDriveApiError('No file was uploaded!', spark_status_code=sparkdrive_resp.status_code)
        else:
            raise self.SparkDriveApiError('SparkDrive file upload.', spark_error=sparkdrive_resp.data, spark_status_code=sparkdrive_resp.status_code)

    def update_member(self, data, member_id=None):
        #update member data:
        sparkdrive_resp = requests.put(
            self.sparkdrive_api2 + '/members' + ('/%s' %(member_id,) if member_id else ''),
            headers=self._get_request_headers(with_secure=True),
            data=data,
        )
        self._parse_sparkdrive_response(sparkdrive_resp)

        if sparkdrive_resp.status_code == 200:
            return True
        else:
            raise self.SparkDriveApiError('SparkDrive update member.', spark_error=sparkdrive_resp.data, spark_status_code=sparkdrive_resp.status_code)
