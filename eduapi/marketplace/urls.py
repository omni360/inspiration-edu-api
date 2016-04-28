from django.conf.urls import patterns, include, url
from marketplace.views import MarketplaceCallbacks


marketplace_urls = patterns('',
    url(r'^/purchase/$', MarketplaceCallbacks.as_view(), name='mkp-purchase'),
)


urlpatterns = patterns('',
    url(r'', include(marketplace_urls)),
)
