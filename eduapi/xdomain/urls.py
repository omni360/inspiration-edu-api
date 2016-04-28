from django.conf.urls import patterns, url
from django.views.generic.base import TemplateView
from django.views.decorators.clickjacking import xframe_options_exempt

urlpatterns = patterns('',
    url(r'proxy\.html$', xframe_options_exempt(TemplateView.as_view(
        template_name='xdomain/proxy.html'
    )), name='xdomain-proxy',),
)
