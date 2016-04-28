import os
from datetime import datetime, timedelta

from django.db import models
from django.conf import settings
from django.utils.timezone import now as utc_now

from utils_app.models import TimestampedModel, DeleteStatusModel
from utils_app.hash import generate_hash

from .state import ClassroomState
from .delegates import OwnerDelegate
from .models import Classroom, Project
from ..auth.models import IgniteUser


class InviteAbstractModel(TimestampedModel, DeleteStatusModel):
    invitee_email = models.EmailField()
    hash = models.CharField(max_length=40, unique=True, default=generate_hash)
    accepted = models.BooleanField(default=False)

    # implement the 'invitee' field and override 'related_name' attribute for this field:
    # invitee = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='{CLASS}_invites', blank=True, null=True)

    #settings:
    default_stale_days = 14

    class Meta(object):
        abstract = True

    def __unicode__(self):
        return 'Invite for %s <%s>' %(self.invitee.name if self.invitee else '', self.invitee_email,)

    def verify_invited_user(self, user):
        """Checks that the given user is the one invited, by matching the email."""
        if user.is_authenticated() and user.email == self.invitee_email:
            return True
        return False

    def accept_invitation(self):
        """Accepts the invitation and does the background logic."""
        raise NotImplementedError('You must define the .accept_invitation() action for the invitation.')

    def decline_invitation(self):
        """Declines the invitation and does the background logic."""
        raise NotImplementedError('You must define the .decline_invitation() action for the invitation.')

    def is_need_invitation(self):
        """Determines whether the invitation is really needed to send email or not."""
        raise NotImplementedError('You must define the .is_need_invitation() action for the invitation.')

    def is_user_already_accepted(self, user):
        """Determines whether the user is already in state as accepted the invitation."""
        raise NotImplementedError('You must define the .is_user_already_accepted() action for the invitation.')

    @staticmethod
    def generate_hash(length=40):
        return generate_hash(length)

    @classmethod
    def delete_stale_invitations(cls, stale_days=None):
        '''
        Deletes stale classroom invitations.
        Default value of life days is read from stale_days (default 14).
        '''
        if stale_days is None:
            stale_days = cls.default_stale_days
        cls.objects.active().filter(
            added__lt=utc_now() - timedelta(days=stale_days)
        ).delete()


class DelegateInvite(InviteAbstractModel):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='delegate_invites')
    invitee = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='delegator_invites', blank=True, null=True)

    default_stale_days = settings.DELEGATE_INVITES_LIFE_DAYS

    def __unicode__(self):
        return 'Invite to delegate from %s for %s <%s>' %(self.owner.name, self.invitee.name if self.invitee else '', self.invitee_email,)

    def accept_invitation(self):
        # Make the user delegated by the owner:
        owner_delegate, _ = OwnerDelegate.objects.get_or_create(owner=self.owner, user=self.invitee)

        # Set accepted to True:
        self.accepted = True
        self.save()

        # Delete (archive) the invite:
        self.delete()

    def decline_invitation(self):
        # Set accepted to False:
        self.accepted = False
        self.save()

        # Delete the invite:
        self.delete()

    def is_need_invitation(self):
        # NOTE: The rational behind this, is that an invitation may be accepted by another user with the same mail,
        #       or even "forwarded" (maybe the same person has 2 mails with 2 different users) to another user.
        # #if user with the invitee_email has is already delegated by the owner - no need to send invitation:
        # if OwnerDelegate.objects.filter(
        #         owner=self.owner,
        #         user__email=self.invitee_email,
        #     ).exists():
        #     return False
        return True

    def is_user_already_accepted(self, user):
        # Whether user is already delegate of the owner.
        if OwnerDelegate.objects.filter(
                owner=self.owner,
                user=user,
            ).exists():
            return True
        return False


class ViewInvite(TimestampedModel):
    project = models.OneToOneField(Project, related_name='view_invite', unique=True)
    hash    = models.CharField(max_length=40, unique=True, default=generate_hash)

    @staticmethod
    def generate_hash(length=40):
        return generate_hash(length)
