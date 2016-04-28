from rest_framework import serializers

from playlists.models import Playlist
from api.serializers import DynamicFieldsModelSerializer, JSONField

class PlaylistSerializer(serializers.ModelSerializer):
    projects = JSONField(source='get_playlist_projects')

    class Meta:
        model = Playlist
        fields = (
            'id',
            'title',
            'description',
            'projects',
        )
