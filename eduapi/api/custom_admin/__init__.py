from .reset_child_password import ChildPasswordResetView
from .projects_review import ProjectsReviewAdmin
from .guardian_moderation import GuardianModerationView
from .arduino_kit_perms import ArduinoKitPermsView
from .analytics import AnalyticsView, AnalyticsPopularView
from .arduino import ArduinoView
from .bad_words_setup import BadWordsSetupView

from django.conf.urls import patterns, include, url
from django.contrib.admin import AdminSite
from api.models import Project

custom_admin_site = AdminSite(name='admin-custom')
custom_admin_urls = patterns('',
    url(r'^/projects-review/', include(ProjectsReviewAdmin(Project, custom_admin_site).urls)),
    url(r'^/coppa-moderation/$', custom_admin_site.admin_view(GuardianModerationView.as_view()), name='coppa-moderation'),
    url(r'^/reset-child-password/$', custom_admin_site.admin_view(ChildPasswordResetView.as_view()), name='child-password-reset'),
    url(r'^/arduino-kit-perms/$', custom_admin_site.admin_view(ArduinoKitPermsView.as_view()), name='arduino-kit-perms'),
    url(r'^/bad-words-setup/$', custom_admin_site.admin_view(BadWordsSetupView.as_view()), name='bad-words-setup'),
    url(r'^/analytics/$', custom_admin_site.admin_view(AnalyticsView.as_view()), name='analytics'),
    url(r'^/analytics-popular/$', custom_admin_site.admin_view(AnalyticsPopularView.as_view()), name='analytics-popular'),
    url(r'^/arduino/$', custom_admin_site.admin_view(ArduinoView.as_view()), name='arduino'),
)
