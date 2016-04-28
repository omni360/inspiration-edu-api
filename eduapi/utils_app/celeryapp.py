import os

from django.conf import settings

from celery import Celery

from celery.schedules import crontab

# set django settings module for celery workers to use django settings:
if not settings.configured:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eduapi.settings')

# create celery app:
app = Celery('celery_app')

# configure celery app:
app.conf.update(
    BROKER_URL=settings.REDIS_URL,
    CELERY_RESULT_BACKEND=settings.REDIS_URL,

    # IMPORTANT NOTES ABOUT REDIS:
    #   1. When using celery with Redis, each celery-worker initializes with 9 redis connections.
    #   2. Each celery task been executed will add 2 more redis connections
    #       (1 for the app input message, 1 for the celery-worker output result message).
    #       Therefore, for each web-worker that runs (or even ran in the past) celery task, it adds 2 connections.
    #
    # Formula to calculate redis connections made by your app (assuming got only 1 celery-worker):
    #   MAX_AMOUNT_REDIS_CONNECTIONS = celery_worker_initial + (web_workers * 2)
    # In addition, in your app, if using django-redis connections pool, then add this number of redis connections increase:
    #   MAX_AMOUNT_REDIS_CONNECTIONS = celery_worker_initial + (web_workers * 2) + (web_workers * num_connections_in_pool)

    CELERYBEAT_SCHEDULE = {
        # Following task logs out users that are unconfirmed for more than 13 days
        'logout-if-not-confirmed': {
            'task': 'api.tasks.logout_non_approved_users', # task name
            'schedule': crontab(hour=settings.LOGOUT_USER_AT_HOUR, minute=settings.LOGOUT_USER_AT_MINUTE), # Executes every day at midnight
            'args': (
                settings.LOGOUT_USER_EVERY_X_DAYS,  # number of days user should be unconfirmed to get logged out
            ),
        },

        # Following task publishes projects that are ready to publish and their min_publish_date has already passed
        'publish-ready-projects': {
            'task': 'api.tasks.publish_ready_projects',
            'schedule': crontab(**getattr(settings, 'PROJECT_PUBLISH_READY_CRONTAB_TIME', {'hour': '*/2', 'minute': '10'})),  #default: run every 2 hours past 10 minutes
        },

        #NOTE: Since email is sent to staff users whenever a project goes into review mode, we disabled this option.
        # # Following task sends emails of projects in review mode to a defined list of emails
        # 'send-emails-of-projects-in-review-summary': {
        #     'task': 'api.tasks.send_staff_emails_of_projects_in_review_summary',
        #     'schedule': crontab(**getattr(settings, 'PROJECTS_IN_REVIEW_SUMMARY_CRONTAB_TIME', {'day_of_week': '1'})),  #default: run every week on sunday
        # },

        # Following task deletes stale delegate invitations
        'delete-stale-delegate-invitations': {
            'task': 'api.tasks.delete_stale_delegate_invites',  # task name
            'schedule': crontab(**getattr(settings, 'DELEGATE_INVITES_DELETE_STALE_CRONTAB_TIME', {'hour': '12', 'minute': '0'})),
        },

        'populate-users-in-states': {
            'task': 'api.tasks.update_remaining_step_states_user', # task name
            'schedule': crontab(minute='*/%d' % settings.RUN_STATE_UPDATE_EVERY_X_MINUTES,
                                hour=settings.RUN_STATE_UPDATE_IN_HOURS_UTC), # Executes every day 5-11 am (0-6 east coast) every 5 minutes
        },

        # Following task fetches 3 last blog posts and put it to cache
        'fetch-blog-posts': {
            'task': 'api.tasks.refresh_three_last_blog_posts',
            'schedule': crontab(minute=0, hour='0-23'),  #default: run every 2 hours past 10 minutes
        },
    }
)

# load all tasks modules of the packages in the list into celery:
app.autodiscover_tasks(
    packages=settings.INSTALLED_APPS
)
