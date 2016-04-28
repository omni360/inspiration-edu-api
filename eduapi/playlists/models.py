from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.core.cache import cache
from api.models import Project

from utils_app.models import TimestampedModel


class Playlist(TimestampedModel):
    TYPE_OTHER = 'other'
    TYPE_FEATURED = 'featured'
    TYPE_HOMEPAGE = 'homepage'
    TYPE_NEW_STUDENT = 'new_student'
    PLAYLIST_TYPES = (
        (TYPE_OTHER, 'Other'),
        (TYPE_FEATURED, 'Featured'),
        (TYPE_HOMEPAGE, 'Homepage'),
        (TYPE_NEW_STUDENT, 'New Student Homepage'),
    )

    title           = models.CharField(max_length=256)
    playlist_type   = models.CharField(choices=PLAYLIST_TYPES,
                                       default=TYPE_OTHER,
                                       max_length=20,
                                       help_text='Setting the playlist as Homepage will change the current Homepage playlist')
    description     = models.CharField(max_length=512, blank=True, null=True)
    project_id_list = ArrayField(models.IntegerField())
    priority        = models.IntegerField(default=0)
    is_published    = models.BooleanField(default=False)

    class Meta:
        ordering = ('priority',)

    def get_playlist_projects(self):
        # Brings cached playlist's projects if it is in cache
        if not cache.get('playlist_projects_%s' % self.pk) and self.is_published:
            # If the projects are not in cache - add them first
            return self._add_playlist_to_cache()
        return cache.get('playlist_projects_%s' % self.pk)

    def save(self, *args, **kwargs):
        # If the playlist is set as Homepage - set the current homepage playlist to type Other
        if self.playlist_type == self.TYPE_HOMEPAGE and self.is_published:
            old_hp_playlists = Playlist.objects.filter(playlist_type=self.TYPE_HOMEPAGE)
            old_hp_playlists.update(playlist_type=self.TYPE_OTHER)

        playlist = super(Playlist, self).save(*args, **kwargs)
        if self.is_published:
            # Invalidate existing caches
            self._invalidate_related_cache()
            # If the project is marked as published - add it to cache
            self._add_playlist_to_cache()
        return playlist

    def _project_to_preview_object(self, project):
        # Fetch projects fields required for presentation and organize them in a dictionary for cache
        # provided fields are used in backend
        return {'id': project.id,
                'title': project.title,
                'cardImage': project.card_image,
                'author': {'name': project.owner.name,
                           'avatar': project.owner.avatar},
                'publishDate': project.publish_date,
                }

    def _add_playlist_to_cache(self):
        # Fetch the projects
        projects = {
            project.id: project for project in
            Project.objects.filter(id__in=self.project_id_list).select_related('owner')
        }
        # Order them according to list
        projects_ordered_list = [self._project_to_preview_object(projects.get(id))
                                  for id in self.project_id_list]
        # Put it to cache
        cache.set('playlist_projects_%s' % self.pk, projects_ordered_list)
        return projects_ordered_list

    def _invalidate_related_cache(self):
        cache.delete_pattern("*playlist*")
        cache.expire('root_view_data', timeout=0)