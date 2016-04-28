import re
import json
import httpretty
from urlparse import urlparse, parse_qs

from django.conf import settings


class MockOxygen(object):

    consumer_key = settings.OXYGEN_CONSUMER_KEY
    users = {
        # 'oxygen_id': {
        #     'is_child': False,
        #     'is_approved': True,
        #     'is_verified_adult': True,
        #     'children': {
        #         'child_ox_id1': {
        #             'moderator_type': 'Parent',
        #         },
        #         'child_ox_id2': {
        #             'moderator_type': 'Education',
        #         },
        #     }
        # },
    }
    authorization_links = {
        # 'auth_code': {
        #     'moderator_id': 'oxygen_id',
        #     'child_id': 'ox_id1',
        # },
    }

    def __init__(self):
        self.users = {}
        self.authorization_links = {}

    def set_mock_user(self, user_oxygen_id, user_data):
        self.users[user_oxygen_id] = user_data
    def remove_mock_user(self, user_oxygen_id):
        self.users.pop(user_oxygen_id, None)
    def get_mock_user(self, user_oxygen_id):
        return self.users.get(user_oxygen_id, None)
    def set_mock_user_as_instance(self, user_obj):
        self.set_mock_user(user_obj.oxygen_id, {
            'is_child': user_obj.is_child,
            'is_approved': user_obj.is_approved,
            'is_verified_adult': user_obj.is_verified_adult,
            'children': {},
        })
        mock_user = self.get_mock_user(user_obj.oxygen_id)
        for ch_link in user_obj.childguardian_child_set.all():
            mock_user['children'][ch_link.child.oxygen_id] = {
                'moderator_type': ch_link.MODERATOR_TYPES_TO_OXYGEN[ch_link.moderator_type],
            }
            if not self.get_mock_user(ch_link.child.oxygen_id):  #if child is not in mock, then add it
                self.set_mock_user_as_instance(ch_link.child)

    def set_mock_authorization_link(self, auth_code, moderator_oxygen_id, child_oxygen_id):
        self.authorization_links[auth_code] = {'moderator_id': moderator_oxygen_id, 'child_id': child_oxygen_id}
    def remove_mock_authorization_link(self, auth_code):
        self.authorization_links.pop(auth_code, None)
    def get_mock_authorization_link(self, auth_code):
        return self.authorization_links.get(auth_code, None)

    def get_child_moderators_list(self, child_oxygen_id):
        return [
            ox_id
            for ox_id, ox_user in self.users.items()
            if child_oxygen_id in ox_user['children']
        ]

    def activate(self, mock_operations=()):
        mock_oxygen = self
        def mock_oxygen_activate_wrapper(func):
            def func_wrapped(*args, **kwargs):
                wrapped_func = httpretty.activate(func)
                mock_oxygen.mock_oxygen_operations(mock_operations)
                return wrapped_func(*args, **kwargs)
            return func_wrapped
        return mock_oxygen_activate_wrapper

    def mock_oxygen_operations(self, operations=()):
        for op in operations:
            getattr(self, '_mock_oxygen_op_' + op)()

    def jsonify_response(self, func):
        def wrapped_func(request, uri, headers):
            status, resp_headers, body = func(request, uri, headers)
            headers.update(resp_headers)
            headers['content-type'] = 'application/json'
            body = json.dumps(body) if body is not None else ''
            return (status, headers, body)
        return wrapped_func

    def _mock_error_response(self, error_code, error_desc, status=400):
        return (status, {}, {
            'error': {
                'errorCode': error_code,
                'errorDescription': error_desc,
            }
        })
    def _assert_response(self, moderator_ox_id, child_ox_id):
        ox_moderator, ox_child = None, None
        if moderator_ox_id:
            ox_moderator = self.get_mock_user(moderator_ox_id)
            if not ox_moderator:
                return self._mock_error_response('ID-CC-008', 'Moderator does not exist in the system.', 404)
            if ox_moderator['is_child']:
               return self._mock_error_response('ID-CC-018', 'Moderator age can not be less than 13 years.')
        if child_ox_id:
            ox_child = self.get_mock_user(child_ox_id)
            if not ox_child:
                return self._mock_error_response('ID-CC-003', 'Child doesn\'t exist in the system.', 404)
            if not ox_child['is_child']:
                return self._mock_error_response('ID-CC-004', 'User is not a child.')
        if ox_moderator and ox_child:
            if child_ox_id not in ox_moderator['children'].keys():
                return self._mock_error_response('ID-CC-017', 'Moderator Id is not linked to the Child Account.')

    def mock_oxygen_3legged_url(self):
        @self.jsonify_response
        def mock_oxygen_3legged_url_body(request, uri, headers):
            uri_qs = parse_qs(urlparse(uri).query)
            return (200, headers, {
                'SIGNED_URL': uri_qs['url'][0]
            })

        httpretty.register_uri(
            httpretty.GET,
            settings.SPARK_DRIVE_API + '/API/V1/A360/SignURL',
            body=mock_oxygen_3legged_url_body,
        )

    def _mock_oxygen_op_get_child_moderators_all(self):
        url_pattern = re.compile('^' + re.escape(settings.OXYGEN_API) + '/api/coppa/v1/child/(?P<child_ox_id>[^/]+)/moderators')

        @self.jsonify_response
        def mock_oxygen_get_child_moderators_all(request, uri, headers):
            child_ox_id, = re.match(url_pattern, uri).groups()
            assert_response = self._assert_response(None, child_ox_id)
            if assert_response:
                return assert_response

            child_moderators = []
            for ox_id, ox_user in self.users.items():
                ch = ox_user.get('children', {}).get(child_ox_id)
                if ch:
                    child_moderators.append({
                        'moderatorId': ox_id,
                        'moderatorStatus': 'Verified' if ox_user['is_verified_adult'] else 'NotVerified',
                        'childType': {'Parent': 'Individual', 'Education': 'Student'}.get(ch['moderator_type'], None),
                    })

            return (200, headers, [{
                'consumerKey': self.consumer_key,
                'moderators': child_moderators,
            }])

        httpretty.register_uri(
            httpretty.GET,
            url_pattern,
            body=mock_oxygen_get_child_moderators_all
        )

        #also mock Oxygen Oauth requests using 3legged:
        self.mock_oxygen_3legged_url()

    def _mock_oxygen_op_get_moderator_children_all(self):
        url_pattern = re.compile('^' + re.escape(settings.OXYGEN_API) + '/api/coppa/v1/moderator/(?P<moderator_ox_id>[^/]+)/children')

        @self.jsonify_response
        def mock_oxygen_get_moderator_children_all(request, uri, headers):
            moderator_ox_id, = re.match(url_pattern, uri).groups()
            assert_response = self._assert_response(moderator_ox_id, None)
            if assert_response:
                return assert_response

            ox_moderator = self.get_mock_user(moderator_ox_id)
            moderator_children = []
            for ox_id, mod_ch in ox_moderator['children'].items():
                ox_ch = self.get_mock_user(ox_id)
                if ox_ch:
                    moderator_children.append({
                        'childId': ox_id,
                        'childAccountStatus': 'Approved' if ox_ch['is_approved'] else 'Restricted',
                        'moderatorType': mod_ch['moderator_type'],
                    })

            return (200, headers, [{
                'consumerKey': self.consumer_key,
                'children': moderator_children,
            }])

        httpretty.register_uri(
            httpretty.GET,
            url_pattern,
            body=mock_oxygen_get_moderator_children_all
        )

        #also mock Oxygen Oauth requests using 3legged:
        self.mock_oxygen_3legged_url()

    def _mock_oxygen_op_get_child_moderator_single(self):
        url_pattern = re.compile('^' + re.escape(settings.OXYGEN_API) + '/api/coppa/v1/moderator/(?P<moderator_ox_id>[^/]+)/child/(?P<child_ox_id>[^/]+)/moderators')

        @self.jsonify_response
        def mock_oxygen_get_child_moderators_all(request, uri, headers):
            moderator_ox_id, child_ox_id = re.match(url_pattern, uri).groups()
            assert_response = self._assert_response(moderator_ox_id, child_ox_id)
            if assert_response:
                return assert_response

            child_moderators = []
            for ox_id, ox_user in self.users.items():
                ch = ox_user.get('children', {}).get(child_ox_id)
                if ch:
                    child_moderators.append({
                        'moderatorId': ox_id,
                        'moderatorStatus': 'Verified' if ox_user['is_verified_adult'] else 'NotVerified',
                        'childType': {'Parent': 'Individual', 'Education': 'Student'}.get(ch['moderator_type'], None),
                    })

            return (200, headers, [{
                'consumerKey': self.consumer_key,
                'moderators': child_moderators,
            }])

        httpretty.register_uri(
            httpretty.GET,
            url_pattern,
            body=mock_oxygen_get_child_moderators_all
        )

    def _mock_oxygen_op_get_child_status(self):
        url_pattern = re.compile('^' + re.escape(settings.OXYGEN_API) + '/api/coppa/v1/child/(?P<child_ox_id>[^/]+)/status')

        @self.jsonify_response
        def mock_oxygen_get_child_status(request, uri, headers):
            child_ox_id, = re.match(url_pattern, uri).groups()
            assert_response = self._assert_response(None, child_ox_id)
            if assert_response:
                return assert_response

            ox_child = self.get_mock_user(child_ox_id)
            child_status = {
                'childAccountStatus': 'Approved' if ox_child['is_approved'] else 'Restricted',
                'childType': 'Student',  #how? she can be moderated both by parent and educator
            }

            return (200, headers, child_status)

        httpretty.register_uri(
            httpretty.GET,
            url_pattern,
            body=mock_oxygen_get_child_status
        )

    def _mock_oxygen_op_add_moderator_children(self):
        url_pattern = re.compile('^' + re.escape(settings.OXYGEN_API) + '/api/coppa/v1/moderator/(?P<moderator_ox_id>[^/]+)/children/approve')

        @self.jsonify_response
        def mock_oxygen_add_moderator_children(request, uri, headers):
            request.POST = json.loads(request.body)

            moderator_ox_id, = re.match(url_pattern, uri).groups()
            assert_response = self._assert_response(moderator_ox_id, None)
            if assert_response:
                return assert_response

            ox_moderator = self.get_mock_user(moderator_ox_id)
            success_children_list = []
            error_list = []
            for consumer_list in request.POST:
                if consumer_list['consumerKey'] == self.consumer_key:
                    for ch_ox_id in consumer_list['childrenIds']:
                        assert_child_error = self._assert_response(None, ch_ox_id)
                        #more assertions:
                        if not assert_child_error:
                            if ch_ox_id in ox_moderator['children'].keys():
                                assert_child_error = (400, {}, {
                                    'error': {
                                        'errorCode': 'ID-CC-029',
                                        'errorDescription': 'The child is already approved by the moderator.',
                                    }
                                })
                        #build 'errorList' from assertion error:
                        if assert_child_error:
                            ch_error = assert_child_error[2]['error']
                            err_dict = next((err for err in error_list if err['errorCode']==ch_error['errorCode']), None)
                            if not err_dict:
                                err_dict = {
                                    'errorCode': ch_error['errorCode'],
                                    'errorDescription': ch_error['errorDescription'],
                                    'consumerChildren': [],
                                }
                                error_list.append(err_dict)
                            err_children_dict = next((err_consumer for err_consumer in err_dict['consumerChildren']
                                                      if err_consumer['consumerKey']==consumer_list['consumerKey'] and err_consumer['moderatorType']==consumer_list['moderatorType']), None)
                            if not err_children_dict:
                                err_children_dict = {
                                    'childIds': [],
                                    'consumerKey': consumer_list['consumerKey'],
                                    'moderatorType': consumer_list['moderatorType'],
                                }
                                err_dict['consumerChildren'].append(err_children_dict)
                            err_children_dict['childIds'].append(ch_ox_id)
                        #build 'success':
                        else:
                            #add child to moderator:
                            ox_moderator['children'][ch_ox_id] ={
                                'moderator_type': consumer_list['moderatorType'],
                            }
                            #approve child:
                            ox_child = self.get_mock_user(ch_ox_id)
                            ox_child['is_approved'] = True
                            success_children_dict = next((c_dict for c_dict in success_children_list if
                                                         c_dict['consumerKey']==consumer_list['consumerKey'] and c_dict['moderatorType']==consumer_list['moderatorType']), None)
                            if not success_children_dict:
                                success_children_dict = {
                                    'childIds': [],
                                    'consumerKey': consumer_list['consumerKey'],
                                    'moderatorType': consumer_list['moderatorType'],
                                }
                                success_children_list.append(success_children_dict)
                            success_children_dict['childIds'].append(ch_ox_id)

            result = {}
            if success_children_list:
                result['success'] = {'consumerChildren': success_children_list}
            if error_list:
                result['errorList'] = error_list
            return (200, headers, result)

        httpretty.register_uri(
            httpretty.POST,
            url_pattern,
            body=mock_oxygen_add_moderator_children
        )

        #also mock GET /api/coppa/v1/moderator/<moderator_id>/child/<child_id>/moderators operation:
        self._mock_oxygen_op_get_child_moderator_single()

    def _mock_oxygen_op_authorize_moderator_child(self):
        url_pattern = re.compile('^' + re.escape(settings.OXYGEN_API) + '/api/coppa/v1/moderator/(?P<moderator_ox_id>[^/]+)/authorizemoderator/(?P<authorization_code>[^/?]+)')

        @self.jsonify_response
        def mock_oxygen_authorize_moderator_child(request, uri, headers):
            moderator_ox_id, authorization_code = re.match(url_pattern, uri).groups()
            assert_response = self._assert_response(moderator_ox_id, None)
            if assert_response:
                return assert_response
            authorization_link = self.get_mock_authorization_link(authorization_code)
            if not authorization_link:
                return self._mock_error_response('ID-CC-015', 'Authorization code is not valid.')
            #add child to moderator:
            ox_moderator = self.get_mock_user(authorization_link['moderator_id'])
            ox_moderator['children'][authorization_link['child_id']] = {
                'moderator_type': 'Parent',
            }
            self.remove_mock_authorization_link(authorization_code)

            result = {
                'authorizeModeratorResult': {
                    'childId': authorization_link['child_id'],
                    'moderatorId': authorization_link['moderator_id'],
                    'moderationStatus': 'Verified' if ox_moderator['is_verified_adult'] else 'NotVerified',
                }
            }
            return (200, headers, result)

        httpretty.register_uri(
            httpretty.PUT,
            url_pattern,
            body=mock_oxygen_authorize_moderator_child
        )

    def _mock_oxygen_op_approve_moderator_child(self):
        url_pattern = re.compile('^' + re.escape(settings.OXYGEN_API) + '/api/coppa/v1/moderator/(?P<moderator_ox_id>[^/]+)/child/(?P<child_ox_id>[^/?]+)')

        @self.jsonify_response
        def mock_oxygen_approve_moderator_child(request, uri, headers):
            request.PUT = json.loads(request.body)

            moderator_ox_id, child_ox_id = re.match(url_pattern, uri).groups()
            assert_response = self._assert_response(moderator_ox_id, child_ox_id)
            if assert_response:
                return assert_response
            child_status = request.PUT.get('childAccount', {}).get('childAccountStatus', None)
            if child_status not in ['Approved', 'Restricted']:
                return self._mock_error_response('ID-CC-002', 'Child account status is invalid')
            #approve child:
            ox_child = self.get_mock_user(child_ox_id)
            child_is_approved = True if child_status=='Approved' else False
            ox_child['is_approved'] = child_is_approved

            return (200, headers, '')

        httpretty.register_uri(
            httpretty.PUT,
            url_pattern,
            body=mock_oxygen_approve_moderator_child
        )

    def _mock_oxygen_op_authorize_and_approve_moderator_child(self):
        self._mock_oxygen_op_authorize_moderator_child()
        self._mock_oxygen_op_approve_moderator_child()

    def _mock_oxygen_op_delete_moderator_child(self):
        url_pattern = re.compile('^' + re.escape(settings.OXYGEN_API) + '/api/coppa/v1/moderator/(?P<moderator_ox_id>[^/]+)/child/(?P<child_ox_id>[^/?]+)')

        @self.jsonify_response
        def mock_oxygen_approve_moderator_child(request, uri, headers):
            moderator_ox_id, child_ox_id = re.match(url_pattern, uri).groups()
            assert_response = self._assert_response(moderator_ox_id, child_ox_id)
            if assert_response:
                return assert_response
            child_status = request.PUT.get('childAccount', {}).get('childAccountStatus', None)
            if child_status not in ['Approved', 'Restricted']:
                return self._mock_error_response('ID-CC-002', 'Child account status is invalid')
            #approve child:
            ox_child = self.get_mock_user(child_ox_id)
            child_is_approved = True if child_status=='Approved' else False
            ox_child['is_approved'] = child_is_approved

            return (200, headers, '')

        httpretty.register_uri(
            httpretty.DELETE,
            url_pattern,
            body=mock_oxygen_approve_moderator_child
        )
