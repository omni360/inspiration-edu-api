import json
import feedparser

from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError
from django.db.models import Q
from django.db.models import Count
from django.core.urlresolvers import reverse
from django.contrib.contenttypes.models import ContentType
from django.contrib.sessions.models import Session
from django.contrib.auth import get_user_model
from django.utils.timezone import now as utc_now
from django.utils.dateparse import parse_datetime
from django.core.cache import cache

from celery.utils.log import get_task_logger
from celery.task import task, Task
from django_redis import get_redis_connection
from notifications.models import Notification, EXTRA_DATA
import sendwithus

from rest_framework.authtoken.models import Token
from six import text_type

from api.auth.models import IgniteUser
import api.models
import marketplace.models

from api.auth.oxygen_operations import OxygenOperations

# import celery app:
from utils_app.celeryapp import app


class SendMailTemplate(Task):
    '''
    This celery task sends bulk of emails template to the given recipients via sendwithus.
    '''
    sendwithus_api = sendwithus.api(api_key=settings.SEND_WITH_US_API_KEY)
    logger = get_task_logger('send_mail_template')
    templates_default_refresh_threshold_hours = 24
    redis_hash_templates = 'SEND_MAIL_TEMPLATE'

    @classmethod
    def get_templates_info(cls):
        '''Returns info dict on the mail templates {load_time, refresh_threshold_hours, is_stale, cur_time}.'''
        redis_conn = get_redis_connection('default')
        templates_refresh_threshold_hours = redis_conn.hget(cls.redis_hash_templates, 'refresh_threshold_hours')
        if not templates_refresh_threshold_hours:  #if not set, set default refresh threshold
            templates_refresh_threshold_hours = 24
            redis_conn.hset(cls.redis_hash_templates, 'refresh_threshold_hours', templates_refresh_threshold_hours)
        templates_refresh_threshold_hours = int(templates_refresh_threshold_hours)
        templates_load_time_str = redis_conn.hget(cls.redis_hash_templates, 'load_time')
        templates_refresh_threshold_timedelta = timedelta(hours=templates_refresh_threshold_hours)
        templates_load_time = parse_datetime(templates_load_time_str) if templates_load_time_str else None
        cur_time = utc_now()
        templates_is_stale = not templates_load_time or cur_time - templates_load_time > templates_refresh_threshold_timedelta
        return {
            'load_time': templates_load_time_str,
            'refresh_threshold_hours': templates_refresh_threshold_hours,
            'is_stale': templates_is_stale,
            'cur_time': str(cur_time),
        }

    @classmethod
    def set_refresh_threshold(cls, timedelta_hours):
        '''Sets the refresh threshold timedelta to consider the templates as stale.'''
        redis_conn = get_redis_connection('default')
        redis_conn.hset(cls.redis_hash_templates, 'refresh_threshold_hours', timedelta_hours)

    @classmethod
    def purge_templates(cls):
        '''Purges the templates, and gets fresh data from server next time needed.'''
        redis_conn = get_redis_connection('default')
        redis_conn.hdel(cls.redis_hash_templates, 'templates_ids', 'load_time')

    @classmethod
    def get_templates(cls, force_refresh=False):
        '''Returns the templates dict. In case of stale data or force to refresh, gets fresh templates list from server.'''
        redis_conn = get_redis_connection('default')
        templates_info = cls.get_templates_info()
        templates_dict = None
        if force_refresh or templates_info['is_stale']:
            resp = cls.sendwithus_api.templates()
            if resp.status_code == 200:
                #make templates dict:
                templates = resp.json()
                templates_dict = {}
                for template in templates:
                    templates_dict[template['name']] = template
                #store templates in Redis email templates hash:
                redis_conn.hset(cls.redis_hash_templates, 'templates', json.dumps(templates_dict))
                redis_conn.hset(cls.redis_hash_templates, 'load_time', templates_info['cur_time'])
            else:
                # TODO: Handle failure.
                cls.logger.critical('Failed to load templates list!')
        #get templates dict from Redis:
        if templates_dict is None:
            templates_dict_json = redis_conn.hget(cls.redis_hash_templates, 'templates')
            templates_dict = json.loads(templates_dict_json) if templates_dict_json else {}
        return templates_dict

    @classmethod
    def get_template_by_name(cls, template_name):
        #return the template data identified by name:
        return cls.get_templates().get(template_name, None)

    def run(self, template_name, emails):
        '''
        This is the function you run for the task.
        Sends bulk email template to the given emails, and returns tuple of (total_emails, total_processed).
        Note that processed emails do not ensure that the email was delivered nor opened.
        Attribute 'emails' is of the given structure: [{ recipient: {address, name?}, email_data?:{<dict>} }, ...]
        [See https://www.sendwithus.com/docs/api#send for more options]
        '''

        # Useful for testing.
        if settings.DISABLE_SENDING_CELERY_EMAILS:
            return 0

        # get template id from name:
        template = self.get_template_by_name(template_name)
        if not template:
            self.logger.error('Email template name \'%s\' was not found!', template_name)
            return False

        # send all emails:
        emails = emails if isinstance(emails, list) else [emails]  #force emails to be a list
        num_emails_sent = 0
        for email in emails:
            # send the email:
            resp = self.sendwithus_api.send(
                email_id=template['id'],
                **email
            )

            if resp.status_code != 200:
                # TODO: Handle failure.
                self.logger.error('Email failed to be sent to: %s <%s>.', email.get('recipient', {}).get('name', ''), email.get('recipient', {}).get('address', ''))
            else:
                self.logger.info('Email successfully sent to: %s <%s>.', email.get('recipient', {}).get('name', ''), email.get('recipient', {}).get('address', ''))
                num_emails_sent += 1

        # return number of successful emails sent:
        return num_emails_sent

#usage: send_mail_template.delay(template_name, emails)
send_mail_template = SendMailTemplate()



@task()
def add_permissions_to_classroom_students(classroom):
    """Adds permissions to the classroom's students as necessary.

    Called after the classroom was updated with new students/projects.

    Adds permissions to the new students/projects.

    Note that this method doesn't handle students/projects that were 
    removed from the classroom.
    """

    Purchase = marketplace.models.Purchase
    ClassroomState = api.models.ClassroomState

    # Get all of the locked projects in the classroom.
    locked_projects = classroom.projects.exclude(lock=api.models.Project.NO_LOCK)

    # Get all of the students in the classroom
    students = classroom.students.filter(classrooms_states__status=ClassroomState.APPROVED_STATUS)

    # Get all of the users who should get a "view" permission to the projects.
    # Those users include:
    #   All of the students in the classroom.
    #   All of the moderators of the students in the classroom.
    users = get_user_model().objects.filter(

        # Students
        Q(id__in=students) | 

        # Moderators
        Q(id__in=api.models.ChildGuardian.objects.filter(
            child_id__in=students
        ).values_list('guardian_id', flat=True))
    )

    # Get all of the existing purchases. This is just an optimization to 
    # reduce the number of requests to the database if the database already 
    # contains the relevant data.
    existing_purchases = [
        (p.project_id, p.user_id) 
        for p 
        in Purchase.objects.filter(project__in=locked_projects, user__in=users)
    ]

    # Go over all of th locked projects and users.
    for lp in locked_projects:
        for u in users:

            # If the student doesn't have a permission to the project.
            if (lp.id, u.id) not in existing_purchases:

                # Try to set a permission. Note that because of race-conditions,
                # even if the purchase doesn't exist in existing_purchases, it 
                # might exist when we reach this point.
                try:
                    Purchase(
                        project_id=lp.id,
                        user_id=u.id,
                        permission=Purchase.VIEW_PERM
                    ).save()

                except IntegrityError:
                    # Purchase already exists - ignore.
                    pass



# region Project Tasks
@task()
def publish_ready_projects():
    ready_projects_to_publish = api.models.Project.objects.filter(
        publish_mode=api.models.Project.PUBLISH_MODE_READY,
        min_publish_date__lte=utc_now(),
    )
    published_projects_ids = []
    for project in ready_projects_to_publish:
        old_publish_mode = project.publish_mode
        project.publish_mode = api.models.Project.PUBLISH_MODE_PUBLISHED
        project.save()
        published_projects_ids.append(project.id)
        project.notify_owner(
            'project_publish_mode_change_by_target',
            {
                'target': None,
                'description': 'Project "%s" published because publication date has arrived - %s.' %(project.title, project.min_publish_date.strftime('%Y-%m-%d %H:%M')),
                'publishMode': project.publish_mode,
                'oldPublishMode': old_publish_mode,
                'publishDate': project.publish_date.strftime('%Y-%m-%d %H:%M'),
            },
            send_mail_with_template='IGNITE_notification_publish_mode_change',
        )
    if published_projects_ids:
        logger = get_task_logger('publish_ready_projects')
        logger.info('Published %i projects that were ready: %s.', len(published_projects_ids), ', '.join([str(x) for x in published_projects_ids]))

@task()
def send_staff_emails_of_projects_in_review_summary():
    """
    Sends summary of projects in review to staff emails list, with predefined max number of last projects in review list.
    """

    recipients          = settings.STAFF_EMAILS
    last_items_limit    = settings.PROJECTS_IN_REVIEW_SUMMARY_LAST_ITEMS_LIMIT

    projects_in_review = api.models.Project.objects.filter(
        publish_mode=api.models.Project.PUBLISH_MODE_REVIEW
    )
    total_projects_in_review = projects_in_review.count()
    if not total_projects_in_review:
        return

    last_projects_in_review = projects_in_review.order_by('-updated')[:last_items_limit]
    projects_in_review_data = {
        'total': total_projects_in_review,
        'last_items': [{
            'id': project.id,
            'title': project.title,
            'author': project.owner.name,
            'updated': project.updated.strftime('%Y-%m-%d %H:%M:%S UTC'),
            'publish_on': project.min_publish_date.strftime('%Y-%m-%d %H:%M UTC') if project.min_publish_date else None,
            'url': settings.IGNITE_FRONT_END_BASE_URL + 'app/project/%s/' %(project.id,)
        } for project in last_projects_in_review],
    }

    emails = []
    for recipient in recipients:
        emails.append({
            'recipient': {
                'address': recipient,
            },
            'email_data': {
                'projects_in_review_admin_url': settings.BASE_URL + reverse('admin-custom:projects-review-changelist'),
                'projects_in_review': projects_in_review_data,
            },
        })
    send_mail_template.run(settings.EMAIL_TEMPLATES_NAMES['PROJECTS_IN_REVIEW_SUMMARY'], emails)
# endregion Project Tasks


# region Notification Tasks
@task()
def notify_user(recipient, actor, verb, **kwargs):
    """
    Handler function to create Notification instance upon action signal call.
    """

    new_notification = Notification(
        recipient = recipient,
        actor_content_type=ContentType.objects.get_for_model(actor),
        actor_object_id=actor.pk,
        verb=text_type(verb),
        public=bool(kwargs.pop('public', False)),
        description=kwargs.pop('description', None),
        timestamp=kwargs.pop('timestamp', utc_now()),
        level=kwargs.pop('level', Notification.LEVELS.info),
    )

    for opt in ('target', 'action_object'):
        obj = kwargs.pop(opt, None)
        if not obj is None:
            setattr(new_notification, '%s_object_id' % opt, obj.pk)
            setattr(new_notification, '%s_content_type' % opt,
                    ContentType.objects.get_for_model(obj))

    if len(kwargs) and EXTRA_DATA:
        new_notification.data = kwargs

    new_notification.save()

    return new_notification


@task()
def notify_and_mail_users(recipients, actor, verb, _mail_template=None, _mail_template_notification_to_email_data=None, **kwargs):
    # Force recipients to be list (iterable):
    recipients = recipients if hasattr(recipients, '__iter__') else [recipients]

    # If send email with template:
    emails = None
    if _mail_template:
        # Import NotificationSerializer for default notification to email data to pass to mail server (defined in NotificationSerializer class):
        if not _mail_template_notification_to_email_data:
            from api.serializers.serializers import NotificationSerializer
            _mail_template_notification_to_email_data = NotificationSerializer().notification_to_email_data
        emails = []

    # Create notification for each recipient:
    new_notification = None
    for recipient in recipients:
        new_notification = notify_user(recipient, actor, verb, **kwargs)

        # Prepare email notification for recipient, when _mail_template is set:
        if _mail_template:
            emails.append({
                'recipient': {
                    'name': recipient.name,
                    'address': recipient.email,
                },
                'email_data': {
                    'notification': _mail_template_notification_to_email_data(new_notification, _mail_template),
                },
            })

    # Send emails about projects (or projects drafts) in review mode to staff emails group
    if new_notification and settings.STAFF_EMAILS and kwargs.get('draftPublishMode', kwargs.get('publishMode', '')) == api.models.Project.PUBLISH_MODE_REVIEW:
        notification_data = _mail_template_notification_to_email_data(new_notification, _mail_template)
        staff_emails = [{
                'recipient': {
                    'name': email,
                    'address': email,
                },
                'email_data': {
                    'notification': notification_data,
                },
            } for email in settings.STAFF_EMAILS]
        if len(staff_emails) > 0:
            emails += staff_emails

    # Send emails notifications:
    if _mail_template and emails:
        send_mail_template.run(_mail_template, emails)
# endregion Notification Tasks


# region Maintenance Tasks
@task()
def fix_lesson_counter(project_id):
    #todo: add cache lock
    project = api.models.Project.objects.filter(id=project_id,
                                                lessons__is_deleted=False
                                                ).annotate(num_lessons=Count('lessons'))[0]
    if project.lesson_count != project.num_lessons:
        project.lesson_count = project.num_lessons
        project.save(update_fields=['lesson_count'])


# Invitations Tasks
@task()
def delete_stale_delegate_invites(stale_days=None):
    api.models.DelegateInvite.delete_stale_invitations(stale_days=stale_days)  # stale_days None defaults to settings.DELEGATE_INVITES_LIFE_DAYS


# User Tasks
@task()
def sync_logged_in_user(user, session_id, session_secure_id):
    #TODO: Handle situation when a child user becomes an adult (maybe handle it in OxygenOperations.sync_child_approved_status?).
    #get Oxygen operations instance, initialized with the SparkDrive session:
    oxygen_operations = OxygenOperations(
        session_id=session_id,
        secure_session_id=session_secure_id
    )

    if user.is_child:
        #check if child user is approved:
        try:
            oxygen_operations.sync_child_approved_status(user)
        except oxygen_operations.OxygenRequestFailed:
            pass  #ignore exception
        #sync all the child's guardians list:
        try:
            oxygen_operations.sync_child_guardians_all(user)
        except oxygen_operations.OxygenRequestFailed:
            pass  #ignore exception

    elif user.is_verified_adult:
        try:
            oxygen_operations.sync_guardian_children(user)
        except oxygen_operations.OxygenRequestFailed:
            pass  #ignore exception

@task()
def logout_non_approved_users(days_to_wait):
    non_approved_users_list = IgniteUser.objects.filter(
                                   is_child=True,
                                   is_approved=False,
                                   added__gte=utc_now() - timedelta(days=days_to_wait)
                               ).values_list('pk', flat=True)
    if len(non_approved_users_list) > 0:
        sessions = Session.objects.all()
        for session in sessions:
            session_uid = session.get_decoded().get('_auth_user_id')
            if session_uid in non_approved_users_list:
                session.delete()

        Token.objects.filter(user__pk__in=non_approved_users_list).delete()

# Adding the user to step and lesson state
@task()
def update_states_user():
    lesson_states = api.models.LessonState.objects.filter(user__isnull=True)[:100]

    for lesson_state in lesson_states:
        user = lesson_state.project_state.user
        lesson_state.step_states.update(user=user)
        lesson_state.user = user
        lesson_state.save(update_fields=['user'])

#todo: add this to scheduler once all the lesson states are populated on prod
@task()
def update_remaining_step_states_user():
    step_states = api.models.StepState.objects.filter(user__isnull=True).select_related('lesson_state', 'lesson_state__project_state')[:100]

    for step_state in step_states:
        step_state.user = step_state.lesson_state.project_state.user
        step_state.save(update_fields=['user'])

@task()
def refresh_three_last_blog_posts():
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


# endregion Maintenance Tasks


