import json
from django.core.cache import cache
from django.core.urlresolvers import reverse

from rest_framework.test import APITestCase
from api.models import Project

from playlists.models import Playlist


class PlaylistTests(APITestCase):
    fixtures = ['test_projects_fixture_1.json']

    @classmethod
    def setUpTestData(cls):
        cls.projects_for_playlist = Project.objects.filter(publish_mode=Project.PUBLISH_MODE_PUBLISHED)[:3]
        cls.projects_ids_for_playlist = [project.id for project in cls.projects_for_playlist]
        cls.playlist = Playlist.objects.create(title='Playlist Title',
                                               project_id_list=cls.projects_ids_for_playlist,
                                               is_published=True)

    def test_created_playlist_is_added_to_cache(self):
        cached_playlist = cache.get('playlist_projects_%s' % self.playlist.id)
        self.assertIsNotNone(cached_playlist)

    def test_created_playlist_contains_proper_project_ids_in_proper_order(self):
        cached_playlist = cache.get('playlist_projects_%s' % self.playlist.id)
        ids = [project.get('id') for project in cached_playlist]
        self.assertListEqual(ids, self.playlist.project_id_list)

    def test_api_get_projects_list(self):
        response = self.client.get(reverse('api:playlist-list',))
        self.assertEquals(response.status_code, 200)
        self.assertEquals(len(response.data[0].get('projects')), 3)

    def test_list_not_in_cache_is_added_after_first_load(self):
        # if playlist in cache - delete it
        if cache.get('playlist_projects_%s' % self.playlist.id):
            cache.delete_pattern("playlist_*")
            cache.delete_pattern("playlists*")
        self.assertIsNone(cache.get('playlist_%s' % self.playlist.id))

        # request the playlist
        response = self.client.get(reverse('api:playlist-list',))
        self.assertEquals(response.status_code, 200)

        # check that playlist was added to cache
        cached_playlist = cache.get('playlist_projects_%s' % self.playlist.id)
        self.assertIsNotNone(cached_playlist)
