from django.conf.urls import patterns, include, url
from playlists.views import PlaylistList, PlaylistDetail
from django.views.decorators.cache import cache_page


playlist_urls = patterns('',
    url(r'^/(?P<pk>\d+)/$', cache_page(60 * 15, key_prefix='playlist')(PlaylistDetail.as_view()), name='playlist-detail'),
    url(r'^/$', PlaylistList.as_view(), name='playlist-list'),
)


urlpatterns = patterns('',
    url(r'', include(playlist_urls)),
)
