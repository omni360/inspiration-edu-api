import urllib

from rest_framework import generics
from rest_framework import permissions
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework import status
from rest_framework import exceptions
from rest_framework.request import clone_request
from django.conf import settings
from django.db.models import Q
from django.shortcuts import get_object_or_404

from rest_framework_bulk import BulkCreateAPIView

from ..tasks import send_mail_template

from .mixins import (
    CacheRootObjectMixin,
    ChoicesOnGet,
    DisableHttpMethodsMixin,
)

from ..serializers import (
    InviterDelegateInviteSerializer,
    InviteeDelegateInviteSerializer,
    ViewInviteSerializer,
)

from ..models import (
    Classroom,
    DelegateInvite,
    IgniteUser,
    ViewInvite, Project,
)

from .permissions import (
    ClassroomPermission,
    ClassroomWriteOnlyPermission,
    IsNotChildOrReadOnly,
    IsNotChild,
    IsReferredProjectOwner,
)


######################
##### BASE VIEWS #####
######################



class DelegateInviteList(ChoicesOnGet, generics.ListCreateAPIView):
    model = DelegateInvite
    queryset = model.objects.active()

    def get_queryset(self):
        qs = super(DelegateInviteList, self).get_queryset()
        #if user is authenticated, get her related invites:
        if self.request.user and self.request.user.is_authenticated():
            qs = qs.active().filter(
                Q(owner=self.request.user) |  #user is delegator owner
                Q(invitee=self.request.user)  #user is delegated invitee
            )
        #else if user is not authenticated, show no invites:
        else:
            qs = qs.none()
        return qs


class DelegateInviteDetail(DisableHttpMethodsMixin, ChoicesOnGet, generics.RetrieveUpdateDestroyAPIView):
    model = DelegateInvite
    lookup_field = 'hash'  #lookup_url_kwarg defaults to this
    disable_http_methods = ['put',]
    queryset = model.objects.active()


class ViewInviteDetail(generics.CreateAPIView, generics.RetrieveDestroyAPIView):
    model = ViewInvite
    lookup_field = 'project_id'
    serializer_class = ViewInviteSerializer
    permission_classes = (IsAuthenticatedOrReadOnly, IsReferredProjectOwner)
    queryset = model.objects.all()

    def perform_create(self, serializer):
        '''
        Set the object's project, based on the incoming request.
        '''
        # # regenerate hash on update:
        # if serializer.instance:
        #     serializer.instance.hash = serializer.instance.generate_hash()
        project_id = self.kwargs.get('project_id', None)
        serializer.save(project_id=project_id)

    def dispatch(self, request, *args, **kwargs):
        # prepare kwargs relying on:
        if 'project_id' in kwargs:
            try:
                project_id = int(kwargs.get('project_id', ''))
            except (ValueError, TypeError):
                project_id = None
            kwargs['project_id'] = project_id

        return super(ViewInviteDetail, self).dispatch(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        project = get_object_or_404(Project, id=self.kwargs.get('project_id', None))
        if hasattr(project, 'view_invite'):
            #when view invite already exists then return the existing view invite:
            return self.retrieve(clone_request(request, 'GET'), *args, **kwargs)
        self.check_object_permissions(self.request, project)
        return super(ViewInviteDetail, self).create(request, *args, **kwargs)

########################
##### NESTED VIEWS #####
########################

# For Inviter:
# ############

class InviterDelegateInviteList(CacheRootObjectMixin, BulkCreateAPIView, DelegateInviteList):
    permission_classes = (IsNotChild,)
    serializer_class = InviterDelegateInviteSerializer

    def get_queryset(self):
        qs = super(InviterDelegateInviteList, self).get_queryset()
        qs = qs.filter(owner=self.request.user)
        return qs

    def get_serializer_context(self):
        context = super(InviterDelegateInviteList, self).get_serializer_context()
        context['owner'] = self.request.user
        return context

    def create(self, request, *args, **kwargs):
        #force create as bulk list:
        bulk_data = request.data if isinstance(request.data, list) else [request.data]

        serializer = self.get_serializer(data=bulk_data, many=True)
        serializer.is_valid(raise_exception=True)
        self.perform_bulk_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    # TODO: move logic of post bulk to celery and call for it from serializer create
    def perform_create(self, serializer):
        self.perform_save(serializer)
    def perform_update(self, serializer):
        self.perform_save(serializer)
    def perform_save(self, serializer):
        objects = serializer.save()

        #send emails to all invitees that have not yet accepted invitation (avoiding resending to invitees that have already accepted):
        emails = [{
            'recipient': {
                'address': obj.invitee_email,
            },
            'email_data': {
                'delegator_name': obj.owner.name,
                'invitation_url': settings.IGNITE_FRONT_END_DASHBOARD_URL + 'myprojects/?' + urllib.urlencode({'collaborateHash': obj.hash}),
            }
        } for obj in objects if not obj.accepted]
        send_mail_template.delay(settings.EMAIL_TEMPLATES_NAMES['DELEGATE_INVITE'], emails)

    def delete(self, request, *args, **kwargs):
        #delete all the active (pending) invites:
        qs = self.get_queryset()
        qs.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# For Invitee:
# ############

class InviteeDelegateInviteDetail(DelegateInviteDetail):
    serializer_class = InviteeDelegateInviteSerializer
    permission_classes = (
        permissions.IsAuthenticatedOrReadOnly,
        IsNotChildOrReadOnly,
    )

    def get_queryset(self):
        queryset = super(InviteeDelegateInviteDetail, self).get_queryset()
        queryset = queryset.select_related(
            'owner',
        )
        return queryset

    def _set_invitee_logged_user(self, obj):
        #if invitee is already set:
        if obj.invitee is not None:
            #check permission (if invitee is already set to the object, assert that it is the logged in user):
            if obj.invitee != self.request.user:
                raise exceptions.PermissionDenied(detail='Only the invitee may change the invitation status.')
            return  #invitee is already set

        #check that invitee is not the owner of the invitation:
        if self.request.user == obj.owner:
            raise exceptions.PermissionDenied(detail='The invitation owner cannot respond to his/her own invitation.')

        #attach the logged in user as the invitee
        obj.invitee = self.request.user

    def perform_update(self, serializer):
        self._set_invitee_logged_user(serializer.instance)

        # Check if current user is already accepted:
        if serializer.instance.is_user_already_accepted(self.request.user):
            raise exceptions.PermissionDenied('You are already a delegate of the invitation owner.')

        # When updated 'accepted' attribute from False to True:
        accepted = serializer.validated_data.get('accepted', None)
        if not serializer.instance.accepted and accepted is not None:
            if accepted == True:
                serializer.instance.accept_invitation()
            elif accepted == False:
                serializer.instance.decline_invitation()

    def perform_destroy(self, instance):
        self._set_invitee_logged_user(instance)
        instance.decline_invitation()

    def post(self, request, *args, **kwargs):
        # Allow POST to update
        return self.update(request, *args, **kwargs)
