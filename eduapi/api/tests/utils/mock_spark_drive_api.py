import json
import httpretty

from django.conf import settings

class MockSparkDriveApi(object):

    @staticmethod
    def mock_spark_drive_token(session_id, secure_session_id):
        httpretty.register_uri(
            httpretty.GET,
            settings.SPARK_DRIVE_API + '/TokenAPI/index.cfm',
            body=json.dumps({
                'LOGIN_AUTHENTICATETOKEN_REPLY': {
                    'SESSION': session_id,
                    'SECURESESSION': secure_session_id,
                }
            }),
            content_type='application/json',
        )
        httpretty.register_uri(
            httpretty.GET,
            settings.SPARK_DRIVE_API + '/api/v2/login/authenticatetoken',
            body=json.dumps({
                'session': session_id,
                'secure_session': secure_session_id,
            }),
            content_type='application/json',
        )

    @staticmethod
    def mock_spark_drive_member(data, with_session=None, omit_fields=None):
        def make_request_member_data(member_data):
            def request_member_data(request, uri, headers):
                if with_session:
                    if request.headers['X-Session'] != with_session['session_id']:
                        return (400, headers, json.dumps({'error': 'Unknown session id!'}))
                return (200, headers, json.dumps(member_data))
            return request_member_data

        omit_fields = omit_fields or []
        v1_result = {
            'MEMBERID': data.get('member_id'),
            'EMAIL': data.get('email'),
            'MEMBERNAME': data.get('name'),
            'MEMBERINITIALNAME': data.get('short_name'),
            'AGE': data.get('age'),
            'OXYGEN_ID': data.get('oxygen_id'),
            'PROFILE': {
                'AVATARPATH': data.get('avatar'),
            },
            'PARENT_EMAIL': data.get('parent_email'),
        }
        [v1_result.pop(f, None) for f in omit_fields]
        httpretty.register_uri(
            httpretty.GET,
            settings.SPARK_DRIVE_API + '/API/v1/Member',
            body=make_request_member_data(v1_result),
            content_type='application/json',
        )
        v2_result = {
            'member': {
                'id': data.get('member_id'),
                'email': data.get('email'),
                'name': data.get('name'),
                'first_name': data.get('short_name'),
                'age': data.get('age'),
                'oxygen_id': data.get('oxygen_id'),
                'profile': {
                    'avatar_path': data.get('avatar'),
                },
                'parent_email': data.get('parent_email'),
            }
        }
        [v2_result['member'].pop(f, None) for f in omit_fields]
        httpretty.register_uri(
            httpretty.GET,
            settings.SPARK_DRIVE_API + '/api/v2/members',
            body=make_request_member_data(v2_result),
            content_type='application/json',
        )
        httpretty.register_uri(
            httpretty.GET,
            settings.SPARK_DRIVE_API + '/api/v2/members/%s' %(v2_result['member']['id'],),
            body=make_request_member_data(v2_result),
            content_type='application/json',
        )

    @staticmethod
    def mock_spark_drive_member_by_oxygen_id(data, with_session=None, omit_fields=None):
        def make_request_member_data(member_data):
            def request_member_data(request, uri, headers):
                if with_session:
                    if request.headers['X-Session'] != with_session['session_id']:
                        return (400, headers, json.dumps({'error': 'Unknown session id!'}))
                return (200, headers, json.dumps(member_data))
            return request_member_data

        omit_fields = omit_fields or []
        v2_result = {
            'member': {
                'id': data.get('member_id'),
                'email': data.get('email'),
                'name': data.get('name'),
                'first_name': data.get('short_name'),
                'age': data.get('age'),
                'oxygen_id': data.get('oxygen_id'),
                'profile': {
                    'avatar_path': data.get('avatar'),
                },
            }
        }
        [v2_result['member'].pop(f, None) for f in omit_fields]
        httpretty.register_uri(
            httpretty.GET,
            settings.SPARK_DRIVE_API + '/api/v2/admin/members/oxygen/%s' %(v2_result['member']['oxygen_id'],),
            body=make_request_member_data(v2_result),
            content_type='application/json',
        )
