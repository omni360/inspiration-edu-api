from django.conf.urls import patterns, include, url
from django.contrib import admin
from django.views.generic import RedirectView

from api.custom_admin import custom_admin_site, custom_admin_urls

from api.urls import lesson_urls, project_urls, classroom_urls, user_urls, invites_urls, auth_urls
from api.views import ApiRoot, BlogView


api_patterns = patterns('',

    url(r'^$', ApiRoot.as_view(), name='root'),
    url(r'^blog/', BlogView.as_view(), name='blog'),

    url(r'^lessons', include(lesson_urls)),
    url(r'^projects', include(project_urls)),
    url(r'^classrooms', include(classroom_urls)),
    url(r'^users', include(user_urls)),
    url(r'^invites', include(invites_urls)),

    url(r'^auth', include(auth_urls)),

    url(r'^mkp', include('marketplace.urls')),

    url(r'^playlists', include('playlists.urls')),

    url(r'^projects', include('analytics.urls')),

    url(r'^docs/', include('rest_framework_swagger.urls')),
)

urlpatterns = patterns('',

    url(r'^api/v1/', include(api_patterns, namespace='api')),

    url(r'instructables-proxy/$', 'utils_app.views.instructables_proxy_view', name='instructables-proxy'),

    url(r'^admin/', include(admin.site.urls)),
    (r'^grappelli/', include('grappelli.urls')),

    url(r'^select2/', include('django_select2.urls')),

    url(r'^apiauth/', include('rest_framework_authtoken_cookie.urls', namespace='rest_framework_authtoken_cookie')),

    url(r'^xdomain/', include('xdomain.urls', namespace='xdomain')),

    #custom admin views:
    url(r'^admin/custom', include(custom_admin_urls, namespace=custom_admin_site.name)),
    # Direct link for editing the homepage Projects' ids. Data migration ensures it has id=1
    url(r'^admin/playlists/playlist/%d/' % ApiRoot.get_homepage_playlist_id(),
        RedirectView.as_view(url='/admin/playlists/playlist/%d/' % ApiRoot.get_homepage_playlist_id(),
                             permanent=True), name='edit-homepage-ids'),
)
