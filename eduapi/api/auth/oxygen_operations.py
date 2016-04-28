import json
import urllib
from django.conf import settings
from django.contrib.auth import get_user_model
from django_redis import get_redis_connection

from utils_app.oxygen_requests import OxygenOauthRequests

from api.models import ChildGuardian


class _OxygenRequestFailed(Exception):
    '''Exception that Oxygen operation request has failed'''
    oxygen_error_code = None
    oxygen_error_desc = None
    def __init__(self, error_msg='', oxygen_error_code='', oxygen_error_desc='', *args, **kwargs):
        if oxygen_error_code:
            self.oxygen_error_code = oxygen_error_code
            oxygen_error_msg = 'Oxygen Error (%s)' %(oxygen_error_code,)
            if oxygen_error_desc:
                self.oxygen_error_desc = oxygen_error_desc
                oxygen_error_msg += ': %s' %(oxygen_error_desc,)
            error_msg = error_msg+' ['+oxygen_error_msg+']' if error_msg else oxygen_error_msg
        super(_OxygenRequestFailed, self).__init__(error_msg, *args, **kwargs)


class OxygenOperations(object):
    #Oxygen OAuth requests gateway object:
    _oxygen_oauth_requests = None

    #Oxygen request failed custom exception:
    OxygenRequestFailed = _OxygenRequestFailed

    def __init__(self, session_id=None, secure_session_id=None):
        self._oxygen_oauth_requests = OxygenOauthRequests(session_id, secure_session_id)

    def _get_redis(self):
        '''Creates a redis connection and returns it'''
        if not getattr(self, 'redis', None):
            self.redis = get_redis_connection('default')
        return self.redis

    def _parse_oxygen_response(self, oxygen_response):
        try:
            oxygen_response.data = oxygen_response.json()
        except ValueError:
            raise self.OxygenRequestFailed('Failed to fetch response (invalid json)!')

    def _get_oxygen_error(self, oxygen_error_response):
        error_code, error_desc = None, None
        if oxygen_error_response.has_key('error'):
            error_code = oxygen_error_response['error'].get('errorCode')
            error_desc = oxygen_error_response['error'].get('errorDescription')
        return error_code, error_desc

    def sync_child_guardians_all(self, child):
        """
        Synchronizes all the guardians of the child user.
        Adds new guardians, and removes deprecated guardians of the child user.
        Note: This is 3-legged OAuth, and the child's session must be used.

        :param child: child user object.
        :return: None. Or throws exception if error in operation.
        """
        #get list of child moderators:
        oxygen_response = self._oxygen_oauth_requests.get_3legged(
            url='/api/coppa/v1/child/%(child_oxg_id)s/moderators' % {
                'child_oxg_id': child.oxygen_id,
            },
            headers={'content-type': 'application/json'},
        )
        self._parse_oxygen_response(oxygen_response)

        #settings - childType in Oxygen response to moderator type in our models:
        child_type_to_moderator_type = {
            'Student': ChildGuardian.MODERATOR_EDUCATOR,
            'Individual': ChildGuardian.MODERATOR_PARENT,
        }
        user_model = get_user_model()

        #SparkDriveApi instance (in case used below):
        sparkdrive_api = None

        #id operation is successful, means guardian is real guardian in Oxygen:
        if oxygen_response.status_code == 200:
            #go ove the consumers lists:
            for consumer_list in oxygen_response.data:
                #only process list for our application consumer key:
                if consumer_list['consumerKey'] == settings.OXYGEN_CONSUMER_KEY:
                    #sync child moderators list:
                    for child_moderator in consumer_list['moderators']:
                        #if moderatorId is not set, then skip this moderator (bug in Oxygen?):
                        if not child_moderator.get('moderatorId'):
                            continue
                        #try get the moderator user object in our database, otherwise skip it:
                        try:
                            #Note: oxygen_id attribute of IgniteUser is unique.
                            guardian_obj = user_model.objects.get(oxygen_id=child_moderator['moderatorId'])
                        except user_model.DoesNotExist:
                            #get user member data through spark drive by oxygen id, and create the user in our system:
                            if sparkdrive_api is None:
                                from spark_drive_operations import SparkDriveOperations
                                sparkdrive_api = SparkDriveOperations(self._oxygen_oauth_requests.session_id, self._oxygen_oauth_requests.secure_session_id)
                            guardian_user_dict = sparkdrive_api.member_data_v2_by_oxygen_id(child_moderator['moderatorId'])
                            if not guardian_user_dict:
                                continue
                            guardian_obj, _ = sparkdrive_api._create_or_update_user_v2(guardian_user_dict)
                        moderation_type = child_type_to_moderator_type[child_moderator['childType']]
                        #link the child and guardian (update moderation type if needed):
                        child_guardian_obj, _ = ChildGuardian.objects.update_or_create(
                            child=child,
                            guardian=guardian_obj,
                            defaults={
                                'moderator_type': moderation_type,
                            }
                        )
                        #in addition, mark guardian user as verified adult in Ignite application, in case verified:
                        if not guardian_obj.is_verified_adult and child_moderator['moderatorStatus'] == 'Verified':
                            guardian_obj.is_verified_adult = True
                            guardian_obj.save()
                    #remove child's guardians that are not in the moderators list:
                    ChildGuardian.objects.filter(
                        child=child
                    ).exclude(
                        guardian__oxygen_id__in=[g['moderatorId'] for g in consumer_list['moderators'] if g.get('moderatorId')]  #skip moderators that moderatorId is not set (bug in Oxygen?)
                    ).delete()
        #else, if operation is not successful:
        else:
            #get the error code and raise exception:
            error_code, error_desc = self._get_oxygen_error(oxygen_response.data)
            raise self.OxygenRequestFailed('Child guardians.', oxygen_error_code=error_code, oxygen_error_desc=error_desc)

    def sync_child_guardian_single(self, child, guardian, sync_all=True):
        """
        Synchronizes the child with the given guardian.

        :param child: child user object.
        :param guardian: guardian user object.
        :param sync_all: whether to sync all guardians of the child, in case list of moderators is successfully returned.
        :return: True if child-guardian are linked, or False. Or throws exception if error in operation.
        """
        #get list of child moderators:
        oxygen_response = self._oxygen_oauth_requests.get(
            url='/api/coppa/v1/moderator/%(guardian_oxg_id)s/child/%(child_oxg_id)s/moderators' % {
                'guardian_oxg_id': guardian.oxygen_id,
                'child_oxg_id': child.oxygen_id,
            },
            headers={'content-type': 'application/json'},
        )
        self._parse_oxygen_response(oxygen_response)

        #settings - childType in Oxygen response to moderator type in our models:
        child_type_to_moderator_type = {
            'Student': ChildGuardian.MODERATOR_EDUCATOR,
            'Individual': ChildGuardian.MODERATOR_PARENT,
        }
        user_model = get_user_model()

        #id operation is successful, means guardian is real guardian in Oxygen:
        if oxygen_response.status_code == 200:
            #go ove the consumers lists:
            for consumer_list in oxygen_response.data:
                #only process list for our application consumer key:
                if consumer_list['consumerKey'] == settings.OXYGEN_CONSUMER_KEY:
                    #sync child moderators list:
                    for child_moderator in consumer_list['moderators']:
                        #if moderatorId is not set, then skip this moderator (bug in Oxygen?):
                        if not child_moderator.get('moderatorId'):
                            continue
                        #if sync_all, then sync all moderators, otherwise sync only the given guardian:
                        if sync_all or child_moderator['moderatorId'] == guardian.oxygen_id:
                            #try get the moderator user object in our database, otherwise skip it:
                            try:
                                #Note: oxygen_id attribute of IgniteUser is unique.
                                guardian_obj = user_model.objects.get(oxygen_id=child_moderator['moderatorId'])
                            except user_model.DoesNotExist:
                                continue
                            moderation_type = child_type_to_moderator_type[child_moderator['childType']]
                            #link the child and guardian (update moderation type if needed):
                            child_guardian_obj, _ = ChildGuardian.objects.update_or_create(
                                child=child,
                                guardian=guardian_obj,
                                defaults={
                                    'moderator_type': moderation_type,
                                }
                            )
                            #in addition, mark guardian user as verified adult in Ignite application, in case verified:
                            if not guardian.is_verified_adult and child_moderator['moderatorStatus'] == 'Verified':
                                guardian.is_verified_adult = True
                                guardian.save()
                    #if sync_all, then remove child's guardians that are not in the moderators list:
                    if sync_all:
                        ChildGuardian.objects.filter(
                            child=child
                        ).exclude(
                            guardian__oxygen_id__in=[g['moderatorId'] for g in consumer_list['moderators']]
                        ).delete()
        #else, if operation is not successful:
        else:
            #get the error code:
            error_code, error_desc = self._get_oxygen_error(oxygen_response.data)
            #if error code is ID-CC-017 (Moderator is not linked to the child), then delete the guardian from the child's guardians list:
            if error_code == 'ID-CC-017':
                ChildGuardian.objects.filter(
                    child=child,
                    guardian=guardian,
                ).delete()
            #any other error, raise an exception:
            else:
                raise self.OxygenRequestFailed('Child guardians.', oxygen_error_code=error_code, oxygen_error_desc=error_desc)

        #return True if child-guardian is linked in our database:
        return ChildGuardian.objects.filter(child=child, guardian=guardian).exists()

    def sync_child_approved_status(self, child):
        """
        Synchronizes the child against Oxygen whther is approved or not.

        :param child: child user object.
        :return: None. Or throws exception if error in operation.
        """
        oxygen_resp = self._oxygen_oauth_requests.get(
            url='/api/coppa/v1/child/%(child_oxg_id)s/status' % {
                'child_oxg_id': child.oxygen_id,
            },
            headers={'content-type': 'application/json'},
        )
        self._parse_oxygen_response(oxygen_resp)

        if oxygen_resp.status_code == 200:
            #check if child is approved:
            child_approved = True if oxygen_resp.data['childAccountStatus'] == 'Approved' else False
            if child.is_approved != child_approved:
                child.is_approved = child_approved
                child.save()
        else:
            error_code, error_desc = self._get_oxygen_error(oxygen_resp.data)
            raise self.OxygenRequestFailed('Child status', oxygen_error_code=error_code, oxygen_error_desc=error_desc)

    def sync_guardian_children(self, guardian):
        """
        Synchronizes the guardian children. Using 3-legged oauth (must init class instance with session_id and secure_session_id).

        :param guardian: guardian user object.
        :return: None. Or throws exception if error in operation.
        """
        #get list of child moderators:
        oxygen_response = self._oxygen_oauth_requests.get_3legged(
            url='/api/coppa/v1/moderator/%(guardian_oxg_id)s/children' % {
                'guardian_oxg_id': guardian.oxygen_id,
            },
            headers={'content-type': 'application/json'},
        )
        self._parse_oxygen_response(oxygen_response)

        #settings - get user model:
        user_model = get_user_model()

        #id operation is successful:
        if oxygen_response.status_code == 200:
            #go ove the consumers lists:
            for consumer_list in oxygen_response.data:
                #only process list for our application consumer key:
                if consumer_list['consumerKey'] == settings.OXYGEN_CONSUMER_KEY:
                    #sync child moderators list:
                    for moderation_child in consumer_list['children']:
                        #try get the child user object in our database, otherwise skip it:
                        try:
                            #Note: oxygen_id attribute of IgniteUser is unique.
                            child_obj = user_model.objects.get(oxygen_id=moderation_child['childId'])
                        except user_model.DoesNotExist:
                            continue
                        moderation_type = ChildGuardian.MODERATOR_TYPES_FROM_OXYGEN[moderation_child['moderatorType']]
                        #link the child and guardian (update moderation type if needed):
                        child_guardian_obj, _ = ChildGuardian.objects.update_or_create(
                            child=child_obj,
                            guardian=guardian,
                            defaults={
                                'moderator_type': moderation_type,
                            }
                        )
                    #remove guardian children that are not in the children list:
                    ChildGuardian.objects.filter(
                        guardian=guardian
                    ).exclude(
                        child__oxygen_id__in=[c['childId'] for c in consumer_list['children']]
                    ).delete()
        #else, if operation is not successful:
        else:
            #get the error code:
            error_code, error_desc = self._get_oxygen_error(oxygen_response.data)
            #if error code is ID-CC-009 (Moderator Id is not linked to any Child Account.), then delete all the children of the guardian:
            if error_code == 'ID-CC-009':
                ChildGuardian.objects.filter(
                    guardian=guardian,
                ).delete()
            #any other error, raise an exception:
            else:
                raise self.OxygenRequestFailed('Guardian children.', oxygen_error_code=error_code, oxygen_error_desc=error_desc)

    def add_guardian_children(self, guardian, moderated_children):
        """
        Adds children to the guardian.

        :param guardian: guardian user object.
        :param moderated_children: dict {<moderation_type>: [list of children users], ...}.
        :return: like moderated_children dict, but each child oxygen id becomes a dict key that has the value of the next dict:
            {
                'child': <IgniteUser child obj>,
                'child_guardian': <ChildGuardian obj>,
                'state': <SUCCESS / ERROR / WARNING>,
                'message': <message>
            }
            Children that are already moderated by the guardian and linked, do have state 'SUCCESS'.
        """
        result = {}
        for moderation_type, children in moderated_children.items():
            result_children = {}

            if children:
                #add children to guardian in Oxygen:
                oxygen_response = self._oxygen_oauth_requests.post(
                    url='/api/coppa/v1/moderator/%(guardian_oxg_id)s/children/approve' % {
                        'guardian_oxg_id': guardian.oxygen_id,
                    },
                    data=json.dumps([{
                        'consumerKey': settings.OXYGEN_CONSUMER_KEY,
                        'moderatorType': ChildGuardian.MODERATOR_TYPES_TO_OXYGEN[moderation_type],
                        'childrenIds': [x.oxygen_id for x in children],
                    }]),
                    headers={'content-type': 'application/json'},
                )
                self._parse_oxygen_response(oxygen_response)

                new_children_hash = {x.oxygen_id: x for x in children}  #make hash on oxygen_id for faster lookup

                if oxygen_response.status_code == 200:
                    if 'success' in oxygen_response.data:
                        #only add successfully saved children in oxygen:
                        for success_consumer_list in oxygen_response.data['success']['consumerChildren']:
                            #only process list for our application consumer key:
                            if success_consumer_list['consumerKey'] == settings.OXYGEN_CONSUMER_KEY:
                                for success_child in success_consumer_list['childIds']:
                                    #link the child to the guardian in our application:
                                    child_obj = new_children_hash.get(success_child)
                                    result_child = {'child': child_obj, 'child_guardian': None, 'state': None, 'message': None}
                                    #link the child and guardian (update moderation type if needed):
                                    child_guardian_obj, _ = ChildGuardian.objects.update_or_create(
                                        child=child_obj,
                                        guardian=guardian,
                                        defaults={
                                            'moderator_type': moderation_type
                                        }
                                    )
                                    result_child['child_guardian'] = child_guardian_obj
                                    #in addition, mark guardian user as verified adult in Ignite application:
                                    if not guardian.is_verified_adult:
                                        guardian.is_verified_adult = True
                                        guardian.save()
                                    #add oxygen response of success:
                                    result_child['state'] = 'SUCCESS'
                                    if not child_obj.is_approved:
                                        child_obj.is_approved = True
                                        child_obj.save()
                                    result_children[success_child] = result_child

                    if 'errorList' in oxygen_response.data:
                        #add messages for children failed to add:
                        for fail_list in oxygen_response.data['errorList']:
                            fail_list_error_code = fail_list['errorCode']
                            for fail_consumer_list in fail_list['consumerChildren']:
                                #only process list for our application consumer key:
                                if fail_consumer_list['consumerKey'] == settings.OXYGEN_CONSUMER_KEY:
                                    for fail_child in fail_consumer_list['childIds']:
                                        child_obj = new_children_hash.get(fail_child)
                                        result_child = {'child': child_obj, 'child_guardian': None, 'state': None, 'message': None}

                                        #errorDescription: "The child is already approved by the moderator":
                                        if fail_list_error_code == 'ID-CC-029':
                                            #try sync the child-guardian, and get the ChildGuardian object, or None otherwise:
                                            try:
                                                is_real_guardian = self.sync_child_guardian_single(child_obj, guardian, sync_all=False)
                                            except self.OxygenRequestFailed:
                                                result_child['state'] = 'ERROR'
                                                result_child['message'] = 'FATAL: The child seems to be already approved by the moderator, but failed to synchronize the moderation type.'
                                            else:
                                                if is_real_guardian:
                                                    child_guardian_obj = ChildGuardian.objects.get(child=child_obj, guardian=guardian)
                                                    result_child['child_guardian'] = child_guardian_obj
                                                    #if moderator type match:
                                                    if child_guardian_obj.moderator_type == moderation_type:
                                                        result_child['state'] = 'SUCCESS'
                                                    #else, moderator type does not match:
                                                    else:
                                                        result_child['state'] = 'WARNING'
                                                        result_child['message'] = 'Child is already moderated by the guardian, but as %s (not as %s)' %(
                                                            dict(ChildGuardian.MODERATOR_TYPE_CHOICES)[child_guardian_obj.moderator_type],
                                                            dict(ChildGuardian.MODERATOR_TYPE_CHOICES)[moderation_type],
                                                        )
                                                else:
                                                    result_child['state'] = 'ERROR'
                                                    result_child['message'] = 'FATAL: The child seems to be already approved by the moderator, but could not find the link in Oxygen.'
                                        #any other error:
                                        else:
                                            result_child['state'] = 'ERROR'
                                            result_child['message'] = fail_list['errorDescription']

                                        result_children[fail_child] = result_child

                else:  #operation failed
                    error_code, error_desc = self._get_oxygen_error(oxygen_response.data)
                    raise self.OxygenRequestFailed('Failed to modify data in Oxygen!', oxygen_error_code=error_code, oxygen_error_desc=error_desc)

            result[moderation_type] = result_children

        #return the moderated children dict with oxygen responses:
        return result

    def authorize_guardian_child(self, guardian, authorization_code):
        """
        Authorizes a child user of a guardian, recognized by the authorization code.

        :param guardian: guardian user object.
        :param authorization_code: authorization code (received via Oxygen email).
        :return: the ChildGuardian link object on success. Or throws exception if error in operation.
        """
        #link the guardian with the child:
        oxygen_resp = self._oxygen_oauth_requests.put(
            url='/api/coppa/v1/moderator/%(guardian_oxg_id)s/authorizemoderator/%(auth_code)s' % {
                'guardian_oxg_id': guardian.oxygen_id,
                'auth_code': authorization_code,
            },
        )
        self._parse_oxygen_response(oxygen_resp)

        #child-guardian was successfully linked:
        if oxygen_resp.status_code == 200:
            #try get the child user in our system:
            user_model = get_user_model()
            try:
                child_obj = user_model.objects.get(oxygen_id=oxygen_resp.data['authorizeModeratorResult']['childId'])
            except user_model.DoesNotExist:
                raise self.OxygenRequestFailed('FATAL: Child user does not exist in our system.')

            #link the child with the guardian in our system:
            child_guardian_obj, _ = ChildGuardian.objects.get_or_create(
                child=child_obj,
                guardian=guardian,
            )

            #return the child guardian link object:
            return child_guardian_obj

        else:
            error_code, error_desc = self._get_oxygen_error(oxygen_resp.data)
            raise self.OxygenRequestFailed('Authorize moderator', oxygen_error_code=error_code, oxygen_error_desc=error_desc)

    def approve_guardian_child(self, guardian, child):
        """
        Approves the child user of a guardian.

        :param guardian: guardian user object.
        :param child: child user object.
        :return: True if approved. Or throws an exception if error in operation.
        """
        oxygen_resp = self._oxygen_oauth_requests.put(
            url='/api/coppa/v1/moderator/%(guardian_oxg_id)s/child/%(child_oxg_id)s' % {
                'guardian_oxg_id': guardian.oxygen_id,
                'child_oxg_id': child.oxygen_id,
            },
            data=json.dumps({
                'childAccount': {
                    'consumerKey': settings.OXYGEN_CONSUMER_KEY,
                    'childAccountStatus': 'Approved',
                },
            }),
            headers={'content-type': 'application/json'},
        )

        if oxygen_resp.status_code == 200:
            #approve the child in our system:
            child.is_approved = True
            child.save()
            return True
        else:
            self._parse_oxygen_response(oxygen_resp)
            error_code, error_desc = self._get_oxygen_error(oxygen_resp.data)
            raise self.OxygenRequestFailed('Link child to guardian', oxygen_error_code=error_code, oxygen_error_desc=error_desc)

    def authorize_and_approve_guardian_child(self, guardian, authorization_code, use_cache_hash=None):
        """
        Authorizes and approves a child user of a guardian, recognized by authorization code.

        :param guardian: guardian user object.
        :param authorization_code: the authorization code.
        :param use_cache_hash: if True, then cache the child id to approve, in case the authorization code becomes
            invalid for any reason (like only the first of the 2 steps was completed).
        :return: the ChildGuardian link object on success. Or throws exception if error in operation.
        """
        #authorize guardian child:
        try:
            child_guardian_obj = self.authorize_guardian_child(guardian, authorization_code)
        except self.OxygenRequestFailed as exc:
            #in case that authorization code is not valid, then try restore the child-guardian link object:
            if exc.oxygen_error_code == 'ID-CC-015':
                #if use cache, then use the hash key to retrieve the child-guardian link object:
                if use_cache_hash:
                    r = self._get_redis()
                    temp_child_id = r.hget(use_cache_hash, 'temp_child_id')
                    try:
                        child_guardian_obj = ChildGuardian.objects.get(guardian=guardian, child_id=temp_child_id)
                    except ChildGuardian.DoesNotExist:
                        raise exc  #otherwise, re-raise the exception
                else:
                    raise exc
            else:
                raise exc
        else:  #authorize guardian child was successful
            #if use cache, then use the hash key to store it in Redis:
            if use_cache_hash:
                r = self._get_redis()
                r.hset(use_cache_hash, 'temp_child_id', child_guardian_obj.child.id)
                r.expire(use_cache_hash, 60 * 60) # Expire in 1 hour

        #approve guardian child:
        if self.approve_guardian_child(guardian, child_guardian_obj.child):
            return child_guardian_obj

    def delete_guardian_child(self, guardian, child, commit_delete=False, reason=None):
        """
        Deletes the child user from Oxygen, using the given guardian.
        Note this will not delete the child object from our system.

        :param guardian: guardian user object
        :param child: child user object
        :param commit_delete: whether to delete the child user from our system.
        :param reason: if set, then sends this reason to Oxygen with the deletion operation.
        :return: True if child was deleted. Or throws exception if error in operation.
        """
        oxygen_resp = self._oxygen_oauth_requests.delete(
            url = '/api/coppa/v1/moderator/%(guardian_oxg_id)s/child/%(child_oxg_id)s' % {
                'guardian_oxg_id': guardian.oxygen_id,
                'child_oxg_id': child.oxygen_id,
            } + (
                '?' + urllib.urlencode([('reason', reason)]) if reason else ''
            ),
            headers={'content-type': 'application/json'},
        )

        if oxygen_resp.status_code == 200:
            #if commit delete, then delete the child user from our system:
            if commit_delete:
                child.delete()
            return True
        else:
            self._parse_oxygen_response(oxygen_resp)
            error_code, error_desc = self._get_oxygen_error(oxygen_resp.data)
            raise self.OxygenRequestFailed('Delete child', oxygen_error_code=error_code, oxygen_error_desc=error_desc)

    def reset_child_password(self, guardian, child, password):
        oxygen_resp = self._oxygen_oauth_requests.put(
            url='/api/coppa/v1/moderator/%(guardian_oxg_id)s/child/%(child_oxg_id)s/resetpassword' % {
                'guardian_oxg_id': guardian.oxygen_id,
                'child_oxg_id': child.oxygen_id,
            },
            data=json.dumps({
                'password': password,
            }),
            headers={'content-type': 'application/json'},
        )

        if oxygen_resp.status_code == 200:
            return True
        else:
            self._parse_oxygen_response(oxygen_resp)
            error_code, error_desc = self._get_oxygen_error(oxygen_resp.data)
            raise self.OxygenRequestFailed('Reset password', oxygen_error_code=error_code, oxygen_error_desc=error_desc)
