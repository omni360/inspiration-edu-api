from rest_framework import serializers
from rest_framework import exceptions

from rest_framework_bulk.serializers import BulkSerializerMixin

from ..models import DelegateInvite, ClassroomState, OwnerDelegate
from .users import UserSerializer
from utils_app.hash import generate_hash


class InviterDelegateInviteListSerializer(serializers.ListSerializer):

    def create(self, validated_data):
        invitees_mails = [invitee.get('invitee_email') for invitee in validated_data]
        owner = self.context.get('owner')

        invites_list = []
        for mail in invitees_mails:
            params = {'owner':owner,
                      'invitee_email':mail}
            #get active invite object:
            invite_obj = self.child.Meta.model.objects.active().filter(**params).first()
            if not invite_obj:
                invite_obj = self.child.Meta.model(hash=generate_hash(), **params)
            if invite_obj.is_need_invitation():
                invite_obj.save()
                invites_list.append(invite_obj)

        return invites_list


class InviterDelegateInviteSerializer(BulkSerializerMixin, serializers.ModelSerializer):
    accepted = serializers.BooleanField(read_only=True)

    inviteeEmail = serializers.EmailField(source='invitee_email', write_only=False, read_only=False)

    class Meta:
        model = DelegateInvite
        fields = (
            'accepted',

            'inviteeEmail',
        )
        list_serializer_class = InviterDelegateInviteListSerializer


class InviteeDelegateInviteSerializer(serializers.ModelSerializer):
    delegator = UserSerializer(source='owner', read_only=True)
    inviter = serializers.SlugRelatedField(source='owner', slug_field='name', read_only=True)

    accepted = serializers.BooleanField(write_only=True, required=True)

    class Meta:
        model = DelegateInvite
        fields = (
            'delegator',
            'inviter',

            'accepted',
        )
