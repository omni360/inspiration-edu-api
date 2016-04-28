"""
Django settings for eduapi project.

For more information on this file, see
https://docs.djangoproject.com/en/dev/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/dev/ref/settings/
"""

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import re, os, dj_database_url
from urlparse import urlparse
from django.conf.global_settings import TEMPLATE_CONTEXT_PROCESSORS as TCP

BASE_DIR = os.path.dirname(os.path.dirname(__file__))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/dev/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('EDUAPI_ENV_SECRET_KEY', '@d8g=tddvgp=k*j1pj5x7dgh1#e2f5ua@iu@oa@po9*x$ft1^c')

DEBUG = (os.environ.get('EDUAPI_ENV_DEBUG', 'FALSE') == 'TRUE')
TEMPLATE_DEBUG = DEBUG

ALLOWED_HOSTS = []
ALLOWED_HOSTS += filter(None, os.environ.get('EDUAPI_ALLOWED_HOSTS', '').split(';'))

# Application definition

INSTALLED_APPS = (
    # 'grappelli',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_counter_field',

    'gunicorn',

    'rest_framework_authtoken_cookie',
    'rest_framework',
    'rest_framework_swagger',
    'rest_framework.authtoken',
    'django_nose',

    'notifications',

    'utils_app',
    'xdomain',
    'edu_token_auth',
    'api',
    'marketplace',
    'playlists',
    'states',
    'analytics',
    'editor_tools',

    'haystack',

    'suit',
    'django_select2',
    'suit_ckeditor',
    'django.contrib.admin',

    # 'debug_toolbar'  #for debug only - keep comment
)

# Base URL
# Warning: Do not use this inside system internals, but only to export links (e.g for emails).
BASE_URL = os.environ.get('EDUAPI_BASE_URL', 'http://localhost')
BASE_PORT = int(os.environ.get('PORT', '5001'))

##################
## Test Runner
TEST_RUNNER = 'django_nose.NoseTestSuiteRunner'
NOSE_ARGS = [
    '--with-coverage',
    '--cover-package=api,xdomain,edu_token_auth',
]

AUTHENTICATION_BACKENDS = (
    'api.auth.authentication_backend.SparkDriveApiBackend',
    'django.contrib.auth.backends.ModelBackend',
)


MIDDLEWARE_CLASSES = (
    'utils_app.remove_bad_cookies.IgnoreBadCookies',  #temporary to bypass python cookies bug (for v2.7.9)

    'sslify.middleware.SSLifyMiddleware',

    'api.crossdomain_middleware.XsSharing',

    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

    'rest_framework_authtoken_cookie.auth_middleware.AuthTokenFromCookie',
)

TEMPLATE_CONTEXT_PROCESSORS = TCP + (
    'django.core.context_processors.request',
)

ROOT_URLCONF = 'eduapi.urls'

# Email Settings
SEND_WITH_US_API_KEY = os.environ.get('SEND_WITH_US_API_KEY', 'live_66080a69524fdea9afc52ba8e2629d3fc0dd9885')
EMAIL_TEMPLATES_NAMES = {
    'ARDUINO_PURCHASE_NOTIFICATION': os.environ.get('EDU_EMAIL_T_ARDUINO_NOTIFICATION', 'IGNITE_arduino_kit_purchase_notification'),
    'CHILD_JOINED_CLASSROOM': os.environ.get('EDU_EMAIL_T_CHILD_JOINED_CLASSROOM', 'Child joined classroom'),
    'CLASSROOM_CODE': os.environ.get('EDU_EMAIL_T_CLASSROOM_CODE', 'IGNITE_classroom_code'),
    'CLASSROOM_INVITE': os.environ.get('EDU_EMAIL_T_CLASSROOM_INVITE', 'IGNITE_classroom_invitation'),
    'DELEGATE_INVITE': os.environ.get('EDU_EMAIL_T_DELEGATE_INVITE', 'IGNITE_delegate_invitation'),
    'PROJECTS_IN_REVIEW_SUMMARY': os.environ.get('EDU_EMAIL_T_PROJECTS_IN_REVIEW_SUMMARY', 'IGNITE_projects_in_review_summary'),
}

# Invites Settings:
DELEGATE_INVITES_LIFE_DAYS = os.environ.get('DELEGATE_INVITES_LIFE_DAYS', 14)
DELEGATE_INVITES_DELETE_STALE_CRONTAB_TIME = {'hour': '12', 'minute': '0'}

# Project Publish Settings:
PROJECT_PUBLISH_READY_CRONTAB_TIME = {'hour': '*/2', 'minute': '10'}

# Projects In Review Summary Settings:
PROJECTS_IN_REVIEW_SUMMARY_CRONTAB_TIME = {'day_of_week': 1}
PROJECTS_IN_REVIEW_SUMMARY_LAST_ITEMS_LIMIT = os.environ.get('EDU_PROJECTS_IN_REVIEW_SUMMARY_LAST_ITEMS_LIMIT', 5)

# FRONT-END URL
IGNITE_FRONT_END_BASE_URL = os.environ.get('IGNITE_FRONT_END_BASE_URL', 'https://projectignite.autodesk.com/')
IGNITE_FRONT_END_DASHBOARD_URL = IGNITE_FRONT_END_BASE_URL + os.environ.get(
    'IGNITE_FRONT_END_DASHBOARD_URL', 'app/dashboard/'
).lstrip('/')
IGNITE_FRONT_END_MODERATION_URL = IGNITE_FRONT_END_DASHBOARD_URL + 'moderation/'


# Django Suit
########
SUIT_CONFIG = {
    # header
    'ADMIN_NAME': 'Edu API',

    'MENU': (
        #keep original:
        'api',
        'marketplace',
        'playlists',
        'auth',
        'authtoken',
        'editor_tools',

        #custom apps:
        {'label': 'Custom Actions', 'models': [
            {'label': 'Projects In Review', 'url': 'admin-custom:projects-review-changelist',},
            {'label': 'COPPA Moderation', 'url': 'admin-custom:coppa-moderation',},
            {'label': 'Reset Children Password', 'url': 'admin-custom:child-password-reset',},
            {'label': 'Arduino Kit Permissons', 'url': 'admin-custom:arduino-kit-perms'},
            {'label': 'Bad Words Setup', 'url': 'admin-custom:bad-words-setup',},
            {'label': 'Edit Homepage Projects IDs', 'url': 'edit-homepage-ids',},
            {'label': 'Analytics', 'url': 'admin-custom:analytics',},
            {'label': 'Popular Projects Analytics', 'url': 'admin-custom:analytics-popular',},
            {'label': 'Arduino Analytics', 'url': 'admin-custom:arduino',},
        ]},
    )
}

# Paypal
# ######
if DEBUG:
    PAYPAL_BASE_URL = 'https://www.sandbox.paypal.com'
    PAYPAL_NVP_BASE_URL = 'https://api-3t.sandbox.paypal.com/nvp'
else:
    PAYPAL_BASE_URL = 'https://www.paypal.com'
    PAYPAL_NVP_BASE_URL = 'https://api-3t.paypal.com/nvp'
PAYPAL_BASE_URL = os.environ.get('PAYPAL_BASE_URL', PAYPAL_BASE_URL)
PAYPAL_NVP_BASE_URL = os.environ.get('PAYPAL_NVP_BASE_URL', PAYPAL_NVP_BASE_URL)
PAYPAL_USERNAME = os.environ.get('PAYPAL_USERNAME', '')
PAYPAL_PASSWORD = os.environ.get('PAYPAL_PASSWORD', '')
PAYPAL_SIGNATURE = os.environ.get('PAYPAL_SIGNATURE', '')
PAYPAL_VERSION = 93

# User Avatar
# ###########

# Used to override O2's default avatar for users. 
# If nothing is defined here, just converts the default avatar from HTTP to HTTPS. 
# The idea is to enable the design team choose the default avatar. 
# We want to be able to store it in the FE and to change it whenever we feel like it.
DEFAULT_USER_AVATAR = os.environ.get('DEFAULT_USER_AVATAR', '')

# Auth
# ####
AUTH_USER_MODEL = 'api.IgniteUser'
SPARK_DRIVE_API = os.environ.get('EDUAPI_SPARK_DRIVE_API', 'https://beta-api.acg.autodesk.com')
SPARK_AFC = os.environ.get('EDUAPI_SPARK_AFC')
SPARK_CLIENT_SECRET = os.environ.get('EDUAPI_SPARK_CLIENT_SECRET')
SPARK_ADMIN_MEMBER_ID = os.environ.get('EDUAPI_SPARK_ADMIN_MEMBER_ID')
OXYGEN_API = os.environ.get('EDUAPI_OXYGEN_API', 'https://accounts-staging.autodesk.com')
OXYGEN_CONSUMER_KEY = os.environ.get('EDUAPI_OXYGEN_CONSUMER_KEY')
OXYGEN_CONSUMER_KEY_SECRET = os.environ.get('EDUAPI_OXYGEN_CONSUMER_KEY_SECRET')

WSGI_APPLICATION = 'eduapi.wsgi.application'

ips = ["10.0.0.%d" %i for i in range(1, 256)]
ips.append('127.0.0.1')
INTERNAL_IPS = tuple(ips)


# Database
DATABASES = {'default': dj_database_url.config()}

# Redis
REDIS_URL = os.getenv('REDISCLOUD_URL', 'redis://localhost:6379')
# Django-Redis
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL,
        'OPTIONS': {
            'CONNECTION_POOL_KWARGS': {
                # IMPORTANT: see comments in celeryapp.py file for redis connection calculations!
                'max_connections': 3,
            }
        }
    }
}


# Internationalization
# https://docs.djangoproject.com/en/dev/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/dev/howto/static-files/

STATIC_URL = '/static/'

# Cross Domain Middleware
# #######################
XS_SHARING_ALLOWED_ORIGINS = '*'
XS_SHARING_ALLOWED_METHODS = ['POST','GET','OPTIONS', 'PUT', 'DELETE']
XS_SHARING_ALLOWED_HEADERS = ['Origin', 'X-Requested-With', 'Content-Type', 'Accept', 'Authorization']


# Django Rest Framework
# #####################

REST_FRAMEWORK = {
    'DEFAULT_FILTER_BACKENDS': (
        # 'backend.filter_backends.NotDeletedFilterBackend',
        'rest_framework.filters.OrderingFilter',
        'rest_framework.filters.SearchFilter',
        'url_filter.integrations.drf.DjangoFilterBackend',
    ),

    'DEFAULT_AUTHENTICATION_CLASSES': (
        'edu_token_auth.authentication.EduTokenAuthentication',
    ),


    # Pagination
    'PAGINATE_BY': 20,                 # Default to 10
    'PAGINATE_BY_PARAM': 'pageSize',   # Allow client to override, using `?pageSize=xxx`.
    'MAX_PAGINATE_BY': 100,            # Maximum limit allowed when using `?pageSize=xxx`.
}

# The following is valid only for Heroku applications (or development).
# When deploying in other environments, you'll need to revisit these settings.

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Disable SSL only in debug mode.
if DEBUG:
    SSLIFY_DISABLE = True

PROJECT_PATH = os.path.dirname(os.path.abspath(__file__))
STATIC_ROOT = 'staticfiles'

STATICFILES_DIRS = (
)

SWAGGER_SETTINGS = {
    "exclude_namespaces": [], # List URL namespaces to ignore
    "api_version": '1',  # Specify your API's version
    "api_path": "/",
    "enabled_methods": [  # Specify which methods to enable in Swagger UI
        'get',
        'post',
        'put',
        'patch',
        'delete'
    ],
    "api_key": '', # An API key
    "is_authenticated": False,  # Set to True to enforce user authentication,
    "is_superuser": False,  # Set to True to enforce admin only access
}


# Haystack Indexer
##################
SEARCHBOX_URL = os.environ.get('SEARCHBOX_URL', False)

if not SEARCHBOX_URL:
    # Local setup
    HAYSTACK_CONNECTIONS = {
        'default': {
            'ENGINE': 'haystack.backends.simple_backend.SimpleEngine',
        },
    }
else:
    es = urlparse(SEARCHBOX_URL)
    port = es.port or 80

    HAYSTACK_CONNECTIONS = {
        'default': {
            'ENGINE': 'haystack.backends.elasticsearch_backend.ElasticsearchSearchEngine',
            'URL': es.scheme + '://' + es.hostname + ':' + str(port),
            'INDEX_NAME': 'projects',
        },
    }

    if es.username:
        HAYSTACK_CONNECTIONS['default']['KWARGS'] = {"http_auth": es.username + ':' + es.password}

# HAYSTACK_SIGNAL_PROCESSOR = 'haystack.signals.RealtimeSignalProcessor'
HAYSTACK_SIGNAL_PROCESSOR = 'api.search_indexes.signals.IgniteSignalProcessor'


# Celery
#########
DISABLE_SENDING_CELERY_EMAILS = False # This is used in tests to disable sending emails by Celery task.

LOGOUT_USER_AT_HOUR = os.environ.get('LOGOUT_USER_AT_HOUR', 12)
LOGOUT_USER_AT_MINUTE = os.environ.get('LOGOUT_USER_AT_MINUTE', 0)
LOGOUT_USER_EVERY_X_DAYS = os.environ.get('LOGOUT_USER_EVERY_X_DAYS', 13)

from datetime import timedelta

BROKER_POOL_LIMIT = 1
CELERYD_CONCURRENCY = os.environ.get('CELERYD_CONCURRENCY', 4) 
BROKER_URL = REDIS_URL
CELERY_TASK_RESULT_EXPIRES = timedelta(minutes=30)
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_IMPORTS = ('api.tasks',) 
CELERY_TIMEZONE = TIME_ZONE
RUN_STATE_UPDATE_EVERY_X_MINUTES = int(os.environ.get('RUN_STATE_UPDATE_EVERY_X_MINUTES', 2))
RUN_STATE_UPDATE_IN_HOURS_UTC = os.environ.get('RUN_STATE_UPDATE_IN_HOURS_UTC', '5,6,7,8,9,10')


# Lesson Applications
# ###################

IGNITE_LESSON_START_URL = IGNITE_FRONT_END_BASE_URL + 'app/'
CIRCUITS_LESSON_START_URL = os.environ.get('EDUAPI_CIRCUITS_LESSON_START_URL', 'https://staging.circuits.io/education/start')
CIRCUITS_LESSON_WITH_ID_START_URL = os.environ.get('EDUAPI_CIRCUITS_LESSON_WITH_ID_START_URL', 'https://staging.circuits.io/education/edit')
TINKERCAD_LESSON_START_URL = os.environ.get('EDUAPI_TINKERCAD_LESSON_START_URL', 'https://www-beta.tinkercad.com/lessons/start')
LAGOA_LESSON_START_URL = os.environ.get('EDUAPI_LAGOA_LESSON_START_URL', 'http://home.lagoa.com/platform/ignite/')

APP_LOGO_BASE_URL = IGNITE_FRONT_END_BASE_URL + 'static/images/'

LESSON_APPS = {
    'Circuits' : {
        'db_name': '123dcircuits',
        'display_name': '123D Circuits',
        'lesson_url': CIRCUITS_LESSON_START_URL,
        'lesson_with_id_url': CIRCUITS_LESSON_WITH_ID_START_URL,
        'logo': '123dcircuits-icon.png',
        'enabled': True,
    },
    'Tinkercad' : {
        'db_name': 'tinkercad',
        'display_name': 'Tinkercad',
        'lesson_url': TINKERCAD_LESSON_START_URL,
        'logo': 'tinkercad-icon.png',
        'enabled': True,
    },
    'Video' : {
        'db_name': 'video',
        'display_name': 'Video',
        'lesson_url': IGNITE_LESSON_START_URL,
        'logo': 'video-icon.png',
        'enabled': True,
    },
    'Step by step': {
        'db_name': 'standalone',
        'display_name': 'Step by step',
        'lesson_url': IGNITE_LESSON_START_URL,
        'logo': 'standalone-icon.png',
        'enabled': os.environ.get('EDUAPI_ENABLE_STANDALONE', 'TRUE') == 'TRUE',
    },
    'Instructables': {
        'db_name': 'instructables',
        'display_name': 'Instructables',
        'lesson_url': IGNITE_LESSON_START_URL,
        'logo': 'instructables-icon.png',
        'enabled': os.environ.get('EDUAPI_ENABLE_INSTRUCTABLES', 'TRUE') == 'TRUE',
    },
    'Lagoa': {
        'db_name': 'lagoa',
        'display_name': 'Lagoa',
        'lesson_url': LAGOA_LESSON_START_URL,
        'logo': 'lagoa-icon.png',
        'enabled': os.environ.get('EDUAPI_ENABLE_LAGOA', 'TRUE') == 'TRUE',
    },
}

LESSON_APPS_ORDER = ['Video', 'Circuits', 'Tinkercad', 'Step by step', 'Instructables', 'Lagoa',]
LESSON_APPS_KEY_FROM_DB_NAME = {v['db_name']: k for k, v in LESSON_APPS.items()}


# Purchases
# #########

# Expects a comma separated string of project IDs.
try:
    ARDUINO_PROJECTS_IDS = map(int, filter(None, re.split('\W+', os.environ.get('EDUAPI_ARDUINO_PROJECTS_IDS', ''))))
except ValueError:
    ARDUINO_PROJECTS_IDS = []
ARDUINO_PURCHASE_IDS = filter(None, os.environ.get('EDUAPI_ARDUINO_PURCHASE_ID', 'ARDUINO-1234').split(','))
MKP_SECRET_TOKEN = os.environ.get('EDUAPI_MKP_SECRET_TOKEN', '123123')


# Notification Settings
# ######################

NOTIFICATIONS_SOFT_DELETE=True
NOTIFICATIONS_USE_JSONFIELD=True


# Django Admin Select2
# #####################

AUTO_RENDER_SELECT2_STATICS = False
SELECT2_BOOTSTRAP = True


# Homepage Projects Settings
##############################
HOMEPAGE_PROJECTS_GROUP_NAME = os.environ.get('EDUAPI_HOMEPAGE_PROJECTS_GROUP_NAME', 'homepage')
try:
    HOMEPAGE_PROJECTS_IDS = map(int, filter(None, re.split('\W+', os.environ.get('EDUAPI_HOMEPAGE_PROJECTS_IDS', ''))))
except ValueError:
    HOMEPAGE_PROJECTS_IDS = []

HOMEPAGE_PLAYLIST_TITLE = os.environ.get('EDUAPI_HOMEPAGE_PLAYLIST_TITLE', 'Homepage')


# Stuff emails for notifications
try:
    STAFF_EMAILS = filter(None, os.environ.get('STAFF_EMAILS', '').split(','))
except ValueError:
    STAFF_EMAILS = []

# Blog url
BLOG_URL = os.environ.get('EDUAPI_BLOG_RSS_LINK', 'http://blog.projectignite.autodesk.com/feed/')