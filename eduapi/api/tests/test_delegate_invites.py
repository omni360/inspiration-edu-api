import json
import unittest

from django.core.urlresolvers import reverse
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone
from django.test.utils import override_settings

from rest_framework.test import APITestCase as DRFTestCase

from .base_test_case import BaseTestCase

from ..models import (
    IgniteUser,
    DelegateInvite,
)

@override_settings(
    CELERY_ALWAYS_EAGER=True,
    BROKER_BACKEND='memory',
    DISABLE_SENDING_CELERY_EMAILS=True)
class DelegateInvitesTest(BaseTestCase, DRFTestCase):
    '''
    Tests the Delegate Invites API.
    '''

    fixtures = ['test_projects_fixture_1.json']

    def setUp(self):
        super(DelegateInvitesTest, self).setUp()

        self.owner = IgniteUser.objects.get(pk=2)
        self.api_delegateinvite_list_url = reverse('api:owner-delegateinvite-list')

        self.post_inviter_invites = [
            {'inviteeEmail': 'user1@test.com'},
            {'inviteeEmail': 'user2@test.com'},
        ]
        self.post_inviter_invites_invalid = [
            {'inviteeEmail': 'invalid-email'},
        ]

        self.patch_invitee_accept = {
            'accepted': True,
        }
        self.patch_invitee_decline = {
            'accepted': False,
        }

    def get_api_self_delegateinvite_detail_url(self, hash):
        return reverse('api:self-delegateinvite-detail', kwargs={'hash': hash})


    # Inviter Tests
    # #############

    def test_only_owner_can_access_delegateinvites(self):
        '''
        Only the owner can access its delegate invites list.
        '''
        # disallow un-authenticated user:
        self.client.force_authenticate(None)
        resp = self.client.get(self.api_delegateinvite_list_url)
        self.assertEqual(resp.status_code, 401)

        # disallow authenticated child user:
        self.client.force_authenticate(IgniteUser.objects.filter(is_child=True).first())
        resp = self.client.get(self.api_delegateinvite_list_url)
        self.assertEqual(resp.status_code, 403)

    def test_owner_get_delegateinvites_list(self):
        '''
        Check that all delegate invites in the list are pending (not accepted).
        '''
        self.client.force_authenticate(self.owner)
        resp = self.client.get(self.api_delegateinvite_list_url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], self.owner.delegate_invites.count())
        self.assertEqual([x['accepted'] for x in resp.data['results']], [False]*resp.data['count'])

    def test_owner_post_delegateinvites(self):
        '''
        Only the owner (not child) can post a new delegate invite.
        '''
        # disallowed child user:
        child = IgniteUser.objects.filter(is_child=True).first()
        self.client.force_authenticate(child)
        num_invites = child.delegate_invites.count()
        resp = self.client.post(
            self.api_delegateinvite_list_url,
            data=json.dumps(self.post_inviter_invites, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(child.delegate_invites.count(), num_invites)

        # allowed user (not child):
        self.client.force_authenticate(self.owner)
        num_invites = self.owner.delegate_invites.count()
        resp = self.client.post(
            self.api_delegateinvite_list_url,
            data=json.dumps(self.post_inviter_invites, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.data), len(self.post_inviter_invites))
        self.assertEqual(self.owner.delegate_invites.count(), num_invites+len(self.post_inviter_invites))

    def test_owner_delete_pending_delegateinvites(self):
        '''
        Only the owner (not child) can delete all the pending delegate invites.
        '''
        # disallowed child user:
        child = IgniteUser.objects.filter(is_child=True).first()
        self.client.force_authenticate(child)
        num_invites = child.delegate_invites.count()
        resp = self.client.delete(
            self.api_delegateinvite_list_url,
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(child.delegate_invites.count(), num_invites)

        # allowed user (not child):
        self.client.force_authenticate(self.owner)
        num_invites = self.owner.delegate_invites.count()
        self.assertGreater(num_invites, 0, 'initial assertion to have some pending invites.')
        resp = self.client.delete(
            self.api_delegateinvite_list_url,
        )
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(self.owner.delegate_invites.count(), 0)

    def test_delegateinvites_disallowed_put(self):
        '''
        PUT method not allowed for delegate invites list.
        '''
        self.client.force_authenticate(self.owner)
        resp = self.client.patch(
            self.api_delegateinvite_list_url,
            data=json.dumps(self.post_inviter_invites, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 405)

    def test_owner_resend_email(self):
        '''
        POSTing an existing pending or declined invitee email will re-send email (old hash for the pending invite, new hash will for the declined invite).
        ### OLD: POSTing an existing accepted invitee email will not re-send email.
        POSTing an existing accepted invitee email will re-send email (new hash).
        '''
        # allowed user (not child):
        self.client.force_authenticate(self.owner)
        delegate_invites = [DelegateInvite.objects.create(owner=self.owner, invitee_email='delegate_invite_%i@test.com'%(i,)) for i in xrange(1,5)]
        accepted_invite = delegate_invites[0]
        accepted_invite.invitee = IgniteUser.objects.create(email=accepted_invite.invitee_email, name='Accepted Invitee User', member_id='temp_user1', oxygen_id='temp_user1')
        accepted_invite.accept_invitation()
        declined_invite = delegate_invites[1]
        declined_invite.invitee = IgniteUser.objects.create(email=declined_invite.invitee_email, name='Declined Invitee User', member_id='temp_user2', oxygen_id='temp_user2')
        declined_invite.decline_invitation()
        pending_invite = delegate_invites[2]
        num_pending_invites = self.owner.delegate_invites.all().count()
        resp = self.client.post(
            self.api_delegateinvite_list_url,
            data=json.dumps([
                {'inviteeEmail': accepted_invite.invitee_email},  #should be ignored
                {'inviteeEmail': declined_invite.invitee_email},  #should be re-sent (new hash)
                {'inviteeEmail': pending_invite.invitee_email},  #should be re-sent (old hash)
            ], cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 201)
        # self.assertEqual(len(resp.data), 2)
        # self.assertEqual(self.owner.delegate_invites.count(), num_pending_invites + 1)
        self.assertEqual(len(resp.data), 3)
        self.assertEqual(self.owner.delegate_invites.count(), num_pending_invites + 2)
        self.assertNotEqual(accepted_invite.hash, self.owner.delegate_invites.get(invitee_email=accepted_invite.invitee_email).hash, 'Accepted invite uses a new hash.')
        self.assertNotEqual(declined_invite.hash, self.owner.delegate_invites.get(invitee_email=declined_invite.invitee_email).hash, 'Declined invite uses a new hash.')
        self.assertEqual(pending_invite.hash, self.owner.delegate_invites.get(invitee_email=pending_invite.invitee_email).hash, 'Pending invite uses the same hash.')


    # Invitee Tests
    # #############

    def test_self_delegateinvite_detail(self):
        pending_invite = self.owner.delegate_invites.all()[0]
        pending_invite_url = self.get_api_self_delegateinvite_detail_url(pending_invite.hash)

        # un-authenticated (allowed):
        self.client.force_authenticate(None)
        resp = self.client.get(pending_invite_url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['delegator']['id'], self.owner.id)
        self.assertEqual(resp.data['inviter'], self.owner.name)

        user = IgniteUser.objects.filter(is_child=False).exclude(id__in=[pending_invite.owner.id]+[x.id for x in pending_invite.owner.delegates.all()]).exclude(email=pending_invite.invitee_email)[0]
        self.client.force_authenticate(user)

        # authenticated - not same email (allowed):
        resp = self.client.get(pending_invite_url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['delegator']['id'], self.owner.id)
        self.assertEqual(resp.data['inviter'], self.owner.name)

    def test_self_delegateinvite_put_method_disabled(self):
        pending_invite = self.owner.delegate_invites.all()[0]
        pending_invite_url = self.get_api_self_delegateinvite_detail_url(pending_invite.hash)

        user = IgniteUser.objects.filter(is_child=False).exclude(id__in=[self.owner.id]+[x.id for x in self.owner.delegates.all()]).exclude(email=pending_invite.invitee_email)[0]
        self.client.force_authenticate(user)
        resp = self.client.put(pending_invite_url)
        self.assertEqual(resp.status_code, 405)

    def test_self_delegateinvite_accept_for_unauthenticated(self):
        pending_invite = self.owner.delegate_invites.all()[0]
        pending_invite_url = self.get_api_self_delegateinvite_detail_url(pending_invite.hash)

        # un-authenticated (disallowed):
        self.client.force_authenticate(None)
        resp = self.client.patch(
            pending_invite_url,
            data=json.dumps(self.patch_invitee_accept, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 401)

    def test_self_delegateinvite_accept_for_authenticated(self):
        pending_invite = self.owner.delegate_invites.all()[0]
        pending_invite_url = self.get_api_self_delegateinvite_detail_url(pending_invite.hash)

        # authenticated (allowed):
        user = IgniteUser.objects.filter(is_child=False).exclude(id__in=[self.owner.id]+[x.id for x in self.owner.delegates.all()]).exclude(email=pending_invite.invitee_email)[0]
        self.client.force_authenticate(user)
        resp = self.client.patch(
            pending_invite_url,
            data=json.dumps(self.patch_invitee_accept, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(user.id, [x.id for x in self.owner.delegates.all()])

    def test_self_delegateinvite_accept_for_invitee_child(self):
        pending_invite = self.owner.delegate_invites.all()[0]
        pending_invite_url = self.get_api_self_delegateinvite_detail_url(pending_invite.hash)

        # create child invitee user:
        invitee_user = IgniteUser.objects.create(name='Invitee User', email=pending_invite.invitee_email, member_id='temp_user1', oxygen_id='temp_user1', is_child=True)
        # authenticated - invitee child (not allowed):
        self.client.force_authenticate(invitee_user)
        resp = self.client.patch(
            pending_invite_url,
            data=json.dumps(self.patch_invitee_accept, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 403)
        self.assertNotIn(invitee_user.id, [x.id for x in self.owner.delegates.all()])

        # cleanup:
        invitee_user.delete()

    def test_self_delegateinvite_accept_for_invitee_owner(self):
        pending_invite = self.owner.delegate_invites.all()[0]
        pending_invite_url = self.get_api_self_delegateinvite_detail_url(pending_invite.hash)

        # invitee is owner (disallow):
        self.client.force_authenticate(self.owner)
        resp = self.client.patch(
            pending_invite_url,
            data=json.dumps(self.patch_invitee_accept, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_self_delegateinvite_accept_for_invitee_delegate(self):
        pending_invite = self.owner.delegate_invites.all()[0]
        pending_invite_url = self.get_api_self_delegateinvite_detail_url(pending_invite.hash)

        # invitee is delegate (disallow):
        invitee_user = self.owner.delegates.first()
        self.client.force_authenticate(invitee_user)
        resp = self.client.patch(
            pending_invite_url,
            data=json.dumps(self.patch_invitee_accept, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_self_delegateinvite_decline_for_auauthenticated(self):
        pending_invite = self.owner.delegate_invites.all()[0]
        pending_invite_url = self.get_api_self_delegateinvite_detail_url(pending_invite.hash)

        # un-authenticated (disallowed):
        self.client.force_authenticate(None)
        resp = self.client.patch(
            pending_invite_url,
            data=json.dumps(self.patch_invitee_decline, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 401)

    def test_self_delegateinvite_decline_for_not_same_email(self):
        pending_invite = self.owner.delegate_invites.all()[0]
        pending_invite_url = self.get_api_self_delegateinvite_detail_url(pending_invite.hash)

        # authenticated - not same email (allowed):
        user = IgniteUser.objects.filter(is_child=False).exclude(id__in=[self.owner.id]+[x.id for x in self.owner.delegates.all()]).exclude(email=pending_invite.invitee_email)[0]
        self.client.force_authenticate(user)
        resp = self.client.patch(
            pending_invite_url,
            data=json.dumps(self.patch_invitee_decline, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(user.id, [x.id for x in self.owner.delegates.all()])

    def test_self_delegateinvite_decline_for_invitee(self):
        pending_invite = self.owner.delegate_invites.all()[0]
        pending_invite_url = self.get_api_self_delegateinvite_detail_url(pending_invite.hash)

        # create invitee user:
        invitee_user = IgniteUser.objects.create(name='Invitee User', email=pending_invite.invitee_email, member_id='temp_user1', oxygen_id='temp_user1')
        # authenticated - invitee (allowed):
        self.client.force_authenticate(invitee_user)
        resp = self.client.patch(
            pending_invite_url,
            data=json.dumps(self.patch_invitee_decline, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(invitee_user.id, [x.id for x in self.owner.delegates.all()])

        # check classroom invite is deleted after declining:
        resp = self.client.get(pending_invite_url)
        self.assertEqual(resp.status_code, 404)

        # cleanup:
        invitee_user.delete()

    def test_self_delegateinvite_decline_for_invitee_child(self):
        pending_invite = self.owner.delegate_invites.all()[0]
        pending_invite_url = self.get_api_self_delegateinvite_detail_url(pending_invite.hash)

        # create child invitee user:
        invitee_user = IgniteUser.objects.create(name='Invitee User', email=pending_invite.invitee_email, member_id='temp_user1', oxygen_id='temp_user1', is_child=True)
        # authenticated - invitee child (not allowed):
        self.client.force_authenticate(invitee_user)
        resp = self.client.patch(
            pending_invite_url,
            data=json.dumps(self.patch_invitee_decline, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 403)
        self.assertNotIn(invitee_user.id, [x.id for x in self.owner.delegates.all()])

        # cleanup:
        invitee_user.delete()

    def test_self_delegateinvite_decline_for_invitee_owner(self):
        pending_invite = self.owner.delegate_invites.all()[0]
        pending_invite_url = self.get_api_self_delegateinvite_detail_url(pending_invite.hash)

        # invitee is owner (disallowed):
        self.client.force_authenticate(self.owner)
        resp = self.client.patch(
            pending_invite_url,
            data=json.dumps(self.patch_invitee_decline, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_self_delegateinvite_decline_for_invitee_delegate(self):
        pending_invite = self.owner.delegate_invites.all()[0]
        pending_invite_url = self.get_api_self_delegateinvite_detail_url(pending_invite.hash)

        # invitee is delegate (disallowed):
        invitee_user = self.owner.delegates.first()
        self.client.force_authenticate(invitee_user)
        resp = self.client.patch(
            pending_invite_url,
            data=json.dumps(self.patch_invitee_decline, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_self_delegateinvite_delete_for_invitee_delegate(self):
        pending_invite = self.owner.delegate_invites.all()[0]
        pending_invite_url = self.get_api_self_delegateinvite_detail_url(pending_invite.hash)

        # invitee is delegate (disallowed):
        invitee_user = self.owner.delegates.first()
        self.client.force_authenticate(invitee_user)
        resp = self.client.delete(
            pending_invite_url,
        )
        self.assertEqual(resp.status_code, 204)

        # check classroom invite is deleted after deleting:
        resp = self.client.get(pending_invite_url)
        self.assertEqual(resp.status_code, 404)

    def test_self_delegateinvite_accept_method_post(self):
        pending_invite = self.owner.delegate_invites.all()[0]
        pending_invite_url = self.get_api_self_delegateinvite_detail_url(pending_invite.hash)

        # create invitee user:
        invitee_user = IgniteUser.objects.create(name='Invitee User', email=pending_invite.invitee_email, member_id='temp_user1', oxygen_id='temp_user1')
        # authenticated - invitee (allowed):
        self.client.force_authenticate(invitee_user)
        resp = self.client.post(
            pending_invite_url,
            data=json.dumps(self.patch_invitee_accept, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(invitee_user.id, [x.id for x in self.owner.delegates.all()])

        # check classroom invite is deleted after accepting:
        resp = self.client.get(pending_invite_url)
        self.assertEqual(resp.status_code, 404)

        # cleanup:
        invitee_user.delete()


    # Background Tasks
    # ################

    @unittest.skip('Not Implemented')
    def test_send_mail_template(self):
        pass

    def test_delete_stale_invitations(self):
        #make stale days to be 1 day less than the oldest valid (pending) invite added time:
        stale_days = (timezone.now() - DelegateInvite.objects.order_by('added')[0].added).days - 1
        num_valid_invites = DelegateInvite.objects.all().filter(added__gt=timezone.now()-timezone.timedelta(days=stale_days)).count()
        num_stale_invites = DelegateInvite.objects.all().filter(added__lte=timezone.now()-timezone.timedelta(days=stale_days)).count()
        self.assertEqual(DelegateInvite.objects.all().count(), num_valid_invites + num_stale_invites)
        DelegateInvite.delete_stale_invitations(stale_days)
        self.assertEqual(DelegateInvite.objects.all().count(), num_valid_invites)
