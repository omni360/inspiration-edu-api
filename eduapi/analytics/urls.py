from django.conf.urls import patterns, include, url

from analytics.views import ProjectAnalyticsView


analytics_urls = patterns('',
    url(r'^/(?P<pk>\d+)/analytics/$', ProjectAnalyticsView.as_view(), name='project-analytics'),
)


urlpatterns = patterns('',
    url(r'', include(analytics_urls)),
)
