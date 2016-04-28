from django.core.cache import cache
from rest_framework import generics
from rest_framework.response import Response

from playlists.models import Playlist
from playlists.serializer import PlaylistSerializer


class PlaylistList(generics.ListAPIView):
    serializer_class = PlaylistSerializer

    def get_queryset(self):
        return Playlist.objects.filter(is_published=True).order_by('priority')

    def list(self, request, *args, **kwargs):
        #todo: add pagination handling
        playlists_list = cache.get('playlists')
        if not playlists_list:
            queryset = self.filter_queryset(self.get_queryset())

            serializer = self.get_serializer(queryset, many=True)
            cache.set('playlists', serializer.data, timeout=None)
            playlists_list = cache.get('playlists')

        return Response(playlists_list)


class PlaylistDetail(generics.RetrieveAPIView):
    serializer_class = PlaylistSerializer

    def get_queryset(self):
        return Playlist.objects.filter(is_published=True)

    def get(self, request, *args, **kwargs):
        pk = self.kwargs.get('pk')
        cached_playlist = cache.get('playlist_%s' % pk)
        if cached_playlist:
            return Response(cached_playlist)
        else:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            cache.set('playlist_%s' % pk, serializer.data, timeout=None)
            return Response(serializer.data)

