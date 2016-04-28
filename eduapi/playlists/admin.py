from django.contrib import admin
from django import forms
from api.models import Project

from .models import Playlist


class PlaylistAdminForm(forms.ModelForm):
    def clean_project_id_list(self):
        # Split the project list and check that every one of them exists and is published
        data = self.cleaned_data['project_id_list']
        for project_id in data:
            if not Project.objects.filter(id=int(project_id), publish_mode=Project.PUBLISH_MODE_PUBLISHED).exists():
                raise forms.ValidationError("The project with id %d does not exist or is not yet published." % int(project_id))
        return data


@admin.register(Playlist)
class PlaylistAdmin(admin.ModelAdmin):
    form = PlaylistAdminForm
    list_display = ['title', 'description', 'project_id_list', 'priority', 'playlist_type', 'is_published',]
