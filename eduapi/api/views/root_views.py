import feedparser

from django.conf import settings
from django.conf.global_settings import LANGUAGES
from django.utils.encoding import force_text
from django.core.cache import cache

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.reverse import reverse
from rest_framework.response import Response

from api.models import Lesson, Project, ProjectGroup
from playlists.models import Playlist


class ApiRoot(APIView):
    """The root for the API. Describes the basics of the API."""

    PERMSISSION_CHOICES = tuple([
        (val, val.capitalize()) for key,val in Project.PERMS.items()
    ])

    LICENSES_URLS = {
        Project.CC_BY_NC_SA_3_0: 'https://creativecommons.org/licenses/by-nc-sa/3.0/',
        Project.CC_BY_SA_3_0: 'https://creativecommons.org/licenses/by-sa/3.0/',
        Project.CC_BY_NC_3_0: 'https://creativecommons.org/licenses/by-nc/3.0/',
        Project.CC_BY_3_0: 'https://creativecommons.org/licenses/by/3.0/',
        Project.PUBLIC_DOMAIN: 'https://creativecommons.org/publicdomain/zero/1.0/',
    }

    # The choices that should be exposed to the client.
    choices = [
        
        # Application choices aren't here because they have special handling.

        {'name': 'difficulty', 'choices': Project.DIFFICULTIES},
        {'name': 'age', 'choices': Project.AGES},
        {'name': 'lock', 'choices': Project.LOCK_CHOICES},
        {'name': 'permission', 'choices': PERMSISSION_CHOICES},
    ]


    def get(self, request):
        cache_data = cache.get('root_view_data', False)
        if cache_data:
            return Response(
                status=status.HTTP_200_OK,
                data=cache_data,
            )
        else:
            data = {
                    'choices': self.get_choices(),
                    'urls': self.get_urls(),
                    'arduinoKitProjectsIds': settings.ARDUINO_PROJECTS_IDS,
                    'homepageProjectsIds': self.get_homepage_project_ids(),
                    'homepagePlaylistId': self.get_homepage_playlist_id(),
                    'homepageNewStudentPlaylistIds': self.get_homepage_new_student_playlist_ids(),
                    'languages': self.get_languages_list(),
                    'playlists': self.get_playlists_dict(),
                    'logosPrefix': settings.APP_LOGO_BASE_URL,
                    'featuredPlaylists': self.get_featured_playlists_ids(),
                    'featureFlags': {
                        'wysiwygTextDirection': True,
                        'wysiwygImg': True,
                        'circuitsCarryOver': True,
                        'newTeacherInfo': True,
                    }
            }
            cache.set('root_view_data', data)
            return Response(
                status=status.HTTP_200_OK,
                data=data,
            )

    def get_choices(self):
        """Parses the choices object and returns a JSON that describes it"""

        choices = { 
            choices['name']: [
                {
                    'v': choice_value,
                    'd': force_text(choice_name, strings_only=True)
                }
                for choice_value, choice_name in choices['choices']
            ] for choices in self.choices 
        }

        # Application choices contain more information per choice, and thus
        # need to have special handling.
        choices['application'] = []
        applications_order = ['Video', 'Circuits', 'Tinkercad', 'Step by step', 'Instructables', 'Lagoa']
        for app_key in applications_order:
            app = settings.LESSON_APPS.get(app_key)
            if app['enabled']:
                choices['application'].append({
                    'v': app['db_name'],
                    'd': app['display_name'],
                    'logo': app['logo'],
                })

        choices['license'] = [
            {
                'v': choice_value,
                'd': force_text(choice_name, strings_only=True),
                'url': self.LICENSES_URLS[choice_value]
            }
            for choice_value, choice_name in Project.LICENSES
        ]


        return choices

    def get_urls(self):
        """A list of URLs that the client can use to interact with the server"""

        return {
            'projects': reverse('api:project-list'),
            'classrooms': reverse('api:classroom-list'),
            'users': reverse('api:user-list'),

            'me': reverse('api:me'),
            'paypalApproval': reverse('api:verify-adult'),
            'myChildren': reverse('api:my-children'),
            'myStudents': reverse('api:my-students'),
        }

    def get_homepage_project_ids(self):
        project_ids = ProjectGroup.get_projects_by_group_name(settings.HOMEPAGE_PROJECTS_GROUP_NAME)
        if project_ids is None:
            project_ids = settings.HOMEPAGE_PROJECTS_IDS
        return project_ids

    def get_playlists_dict(self):
        playlists = Playlist.objects.values_list('id', 'title') # should we limit it?
        return {playlist[1]: playlist[0] for playlist in playlists}

    @staticmethod
    def get_homepage_playlist_id():
        # try to fetch the playlist by type
        playlist_ids = Playlist.objects.filter(playlist_type=Playlist.TYPE_HOMEPAGE).values_list('id', flat=True)
        if len(playlist_ids) > 0:
            return playlist_ids[0]

        # If playlist was not found by type try to find playlist by name
        playlist_ids = Playlist.objects.filter(title=settings.HOMEPAGE_PLAYLIST_TITLE).values_list('id', flat=True)
        # return playlist ID
        if len(playlist_ids) > 0:
            return playlist_ids[0]
        # or return 0
        else:
            return 0

    def get_homepage_new_student_playlist_ids(self):
        # try to fetch the playlist by type
        return Playlist.objects.filter(playlist_type=Playlist.TYPE_NEW_STUDENT).values_list('id', flat=True)

    def get_featured_playlists_ids(self):
        return Playlist.objects.filter(playlist_type=Playlist.TYPE_FEATURED).values_list('id', flat=True)

    def get_languages_list(self):
        return [
            ["ar","Arabic"],
            ["da","Danish"],
            ["de","German"],
            ["el","Greek"],
            ["en","English"],
            ["es","Spanish"],
            ["fr","French"],
            ["he","Hebrew"],
            ["it","Italian"],
            ["ja","Japanese"],
            ["nl","Dutch"],
            ["pt","Portuguese"],
            ["ru","Russian"],
            ["tr","Turkish"],
            ["zh-cn","Simplified Chinese"],
            ["zh-tw","Traditional Chinese"]
        ]


class BlogView(APIView):
    def get(self, request):
        data = cache.get('blog_rss', False)
        if data:
            return Response(
                status=status.HTTP_200_OK,
                data=data,
            )
        else:
            feed = feedparser.parse(settings.BLOG_URL)
            entries = [
                {
                    'title': entry.get('title'),
                    'body': entry.get('summary')[:150],
                    'author': entry.get('author'),
                    'link': entry.get('link'),
                    'published': entry.get('published'),
                    'media_thumbnail': entry.get('media_thumbnail')[0].get('url'),
                 }
                for entry in feed['entries'][:3]
            ]
            cache.set('blog_rss', entries)
            return Response(
                status=status.HTTP_200_OK,
                data=entries,
            )
