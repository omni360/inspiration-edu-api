from rest_framework import generics
from rest_framework.response import Response
from rest_framework import status

from notifications.models import Notification

from api.serializers import NotificationSerializer
from api.views.permissions import IsRecipient
from api.views.filters import NotificationFilter


class NotificationsList(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = (IsRecipient, )
    filter_class = NotificationFilter

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user).active()


class UnreadNotificationsList(NotificationsList):
    def get_queryset(self):
        queryset = super(UnreadNotificationsList, self).get_queryset()
        queryset = queryset.unread()
        return queryset

    def put(self, request, *args, **kwargs):
        Notification.objects.mark_all_as_read(recipient=self.request.user)
        return Response(status=status.HTTP_200_OK)

    def patch(self, request, *args, **kwargs):
        Notification.objects.mark_all_as_read(recipient=self.request.user)
        return Response(status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):
        Notification.objects.mark_all_as_read(recipient=self.request.user)
        return Response(status=status.HTTP_200_OK)


class ReadNotificationsList(NotificationsList):
    def get_queryset(self):
        queryset = super(ReadNotificationsList, self).get_queryset()
        queryset = queryset.read()
        return queryset

    def put(self, request, *args, **kwargs):
        Notification.objects.mark_all_as_unread(recipient=self.request.user)
        return Response(status=status.HTTP_200_OK)

    def patch(self, request, *args, **kwargs):
        Notification.objects.mark_all_as_unread(recipient=self.request.user)
        return Response(status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):
        Notification.objects.mark_all_as_unread(recipient=self.request.user)
        return Response(status=status.HTTP_200_OK)


class UnreadNotificationsDetail(generics.UpdateAPIView):
    serializer_class = NotificationSerializer
    permission_classes = (IsRecipient, )

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user).active()

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.mark_as_read()
        return Response(status=status.HTTP_200_OK)


class RereadNotificationsDetail(generics.UpdateAPIView):
    serializer_class = NotificationSerializer
    permission_classes = (IsRecipient, )

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user).active()

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.mark_as_unread()
        return Response(status=status.HTTP_200_OK)

