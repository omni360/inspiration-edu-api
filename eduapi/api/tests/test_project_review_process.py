import json
import copy
import unittest
import mock

from django.conf import settings
from django.db.models import Q, Count
from django.core.urlresolvers import reverse
from django.contrib.auth import get_user_model
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.dateparse import parse_datetime
from django.utils.timezone import timedelta, now as utc_now
from django.test.utils import override_settings

from rest_framework.test import APITestCase as DRFTestCase
from .base_test_case import BaseTestCase, mock_sendwithus_templates

from api.tasks import (
    publish_ready_projects,
    notify_and_mail_users,
    notify_user,
    send_mail_template,
    send_staff_emails_of_projects_in_review_summary,
)

from ..models import (
    Project,
    Lesson,
    OwnerDelegate,
)


@override_settings(
    STAFF_EMAILS=['a@test.com2', 'b@test.com2'],
    PROJECTS_IN_REVIEW_SUMMARY_LAST_ITEMS_LIMIT=3,
)
class ProjectReviewProcessTests(BaseTestCase, DRFTestCase):

    fixtures = ['test_projects_fixture_1.json']
    model = Project

    def setUp(self, *args, **kwargs):
        super(ProjectReviewProcessTests, self).setUp(*args, **kwargs)

        notify_user.app.conf.CELERY_ALWAYS_EAGER = True
        notify_and_mail_users.app.conf.CELERY_ALWAYS_EAGER = True

        self.api_detail = 'api:project-detail'
        self.api_change_mode_detail = 'api:project-detail'

        self.owner_user = get_user_model().objects.annotate(
            num_delegates=Count('delegates'),
        ).filter(
            is_superuser=False,
            is_child=False,
            num_delegates__gte=1,
        ).first()

        self.reviewer_user = get_user_model().objects.exclude(
            pk=self.owner_user.pk,
        ).filter(
            is_superuser=False,
            is_child=False,
        ).first()
        self.reviewer_user.is_superuser = True
        self.reviewer_user.save()

        self.client.force_authenticate(self.owner_user)


    def _get_new_project_with_lessons(self, num_lessons=3):
        project = Project.objects.create(
            owner=self.owner_user,
            title='Testing 101',
            description='Learn how to test Django applications using Python\'s unittest',
            duration=45,
            banner_image='http://placekitten.com/2048/640/',
            card_image='http://placekitten.com/1024/768/',
            age=Project.AGES[0][0],
            difficulty=Project.DIFFICULTIES[0][0],
            license=Project.LICENSES[0][0],
            ngss=[Project.NGS_STANDARDS[0][0], Project.NGS_STANDARDS[1][0]],
            ccss=[Project.CCS_STANDARDS[0][0], Project.CCS_STANDARDS[1][0]],
            subject=[Project.SUBJECTS[0][0], Project.SUBJECTS[1][0]],
            technology=[Project.TECHNOLOGY[0][0], Project.TECHNOLOGY[1][0]],
            grades_range=[Project.GRADES[0][0], Project.GRADES[1][0]],
            skills_acquired=['3D-printing', '3D-modeling'],
            learning_objectives=['Mesh', 'Shaders'],
            four_cs_creativity='<p>Creativity</p>',
            four_cs_critical='<p>Critical</p>',
            four_cs_communication='<p>Communication</p>',
            four_cs_collaboration='<p>Collaboration</p>',
        )
        for i in xrange(0, num_lessons):
            project.lessons.create(
                title='Lesson 101 - %s' %(i,),
                application='video',
                application_blob={'video': {'vendor': 'youtube', 'id': '1234567890a'}},
                duration=30,
                order=i,
            )
        return project

    def _check_notifications(self, project, user, to_mode, from_mode, mock_send):
        # Check notifications:
        project_owner_and_delegates_qs = get_user_model().objects.filter(Q(pk=project.owner.pk) | Q(pk__in=project.owner.delegates.all()))
        for delegate in project_owner_and_delegates_qs:
            notification = delegate.notifications.filter(
                verb__in=['project_publish_mode_change_by_target', 'project_publish_mode_change_by_target_with_feedback'],
                actor_content_type__model=Project._meta.model_name,
                actor_object_id=project.pk,
            ).order_by(
                '-timestamp'
            ).first()
            self.assertEqual(notification.target, user)
            self.assertEqual(notification.data['publishMode'], to_mode)
            self.assertEqual(notification.data['oldPublishMode'], from_mode)

        # Check notification emails sent:
        executed_emails_set = {call[1]['recipient']['address'] for call in mock_send.call_args_list}
        expected_emails = [delegate.email for delegate in project_owner_and_delegates_qs]
        if to_mode == Project.PUBLISH_MODE_REVIEW:
            expected_emails_set = set(expected_emails + settings.STAFF_EMAILS)
        else:
            expected_emails_set = set(expected_emails)
        self.assertSetEqual(executed_emails_set, expected_emails_set,
                            msg='Notification should be sent to all editors (project owner and her delegates).'
        )

    @mock.patch.object(send_mail_template.sendwithus_api, 'templates', mock_sendwithus_templates)
    @mock.patch.object(send_mail_template.sendwithus_api, 'send')
    def _test_can_change_mode(self, project, user, to_mode, from_mode, mock_send):
        if user:
            self.client.force_authenticate(user)

        old_publish_mode = project.publish_mode
        if from_mode:
            project.publish_mode = from_mode
            project.save()

        old_min_publish_date = project.min_publish_date
        if to_mode == Project.PUBLISH_MODE_READY:
            project.min_publish_date = utc_now() + timedelta(days=1)
            project.save()
        elif to_mode == Project.PUBLISH_MODE_PUBLISHED:
            project.min_publish_date = None
            project.save()
            project.registrations.create(user=get_user_model().objects.first())
            self.assertGreater(project.registrations.count(), 0)

        resp = self.client.patch(
            reverse(self.api_change_mode_detail, kwargs={'pk': project.pk}),
            json.dumps({
                'publishMode': to_mode,
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['publishMode'], to_mode)

        self._check_notifications(project, user, to_mode, from_mode, mock_send)

        # Re-get project
        project = Project.objects.get(pk=project.pk)
        self.assertEqual(project.publish_mode, to_mode)
        if to_mode == Project.PUBLISH_MODE_PUBLISHED:
            self.assertEqual(project.publish_date, project.updated)
            self.assertEqual(project.registrations.count(), 0)
        else:
            self.assertIsNone(project.publish_date)

        # Clean
        project.publish_mode = old_publish_mode
        project.min_publish_date = old_min_publish_date
        project.save()

    @mock.patch.object(send_mail_template.sendwithus_api, 'templates', mock_sendwithus_templates)
    @mock.patch.object(send_mail_template.sendwithus_api, 'send')
    def _test_cannot_change_mode(self, project, user, to_mode, from_mode, mock_send):
        if user:
            self.client.force_authenticate(user)

        old_publish_mode = project.publish_mode
        if from_mode:
            project.publish_mode = from_mode
            project.save()

        old_min_publish_date = project.min_publish_date
        if to_mode == Project.PUBLISH_MODE_READY:
            project.min_publish_date = utc_now() + timedelta(days=1)
            project.save()
        elif to_mode == Project.PUBLISH_MODE_PUBLISHED:
            project.min_publish_date = None
            project.save()

        resp = self.client.patch(
            reverse(self.api_change_mode_detail, kwargs={'pk': project.pk}),
            json.dumps({
                'publishMode': to_mode,
            }),
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [400, 403])
        if resp.status_code == 400:
            self.assertIn('publishMode', resp.data)

        # Re-get project
        project = Project.objects.get(pk=project.pk)
        self.assertEqual(project.publish_mode, from_mode)

        # Clean
        if project.min_publish_date != old_min_publish_date:
            project.min_publish_date = old_min_publish_date
            project.save()

    @mock.patch.object(send_mail_template.sendwithus_api, 'templates', mock_sendwithus_templates)
    @mock.patch.object(send_mail_template.sendwithus_api, 'send')
    def _test_can_change_min_publish_date(self, project, user, with_publish_mode, min_publish_date, mock_send):
        self.client.force_authenticate(user)

        old_publish_mode = project.publish_mode
        if with_publish_mode != project.publish_mode:
            project.publish_mode = with_publish_mode
            project.save()
        old_min_publish_date = project.min_publish_date

        resp = self.client.patch(
            reverse(self.api_change_mode_detail, kwargs={'pk': project.pk}),
            json.dumps({
                'minPublishDate': None if not min_publish_date else min_publish_date.isoformat(),
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(None if resp.data['minPublishDate'] is None else parse_datetime(resp.data['minPublishDate']), min_publish_date)

        # Re-get project
        project = Project.objects.get(pk=project.pk)
        self.assertEqual(project.min_publish_date, min_publish_date)

        # Check automatically published if was in ready mode and changed to min publish date in the past:
        if with_publish_mode == Project.PUBLISH_MODE_READY and (project.min_publish_date is None or project.min_publish_date < utc_now()):
            self.assertEqual(project.publish_mode, Project.PUBLISH_MODE_PUBLISHED)
            self._check_notifications(project, user, Project.PUBLISH_MODE_PUBLISHED, Project.PUBLISH_MODE_READY, mock_send)
        else:
            self.assertEqual(project.publish_mode, with_publish_mode)
            self.assertFalse(mock_send.called)

        # Clean
        project.publish_mode = old_publish_mode
        project.min_publish_date = old_min_publish_date
        project.save()

    @mock.patch.object(send_mail_template.sendwithus_api, 'templates', mock_sendwithus_templates)
    @mock.patch.object(send_mail_template.sendwithus_api, 'send')
    def _test_cannot_change_min_publish_date(self, project, user, with_publish_mode, min_publish_date, mock_send):
        self.client.force_authenticate(user)

        old_publish_mode = project.publish_mode
        if with_publish_mode != project.publish_mode:
            project.publish_mode = with_publish_mode
            project.save()
        old_min_publish_date = project.min_publish_date

        resp = self.client.patch(
            reverse(self.api_change_mode_detail, kwargs={'pk': project.pk}),
            json.dumps({
                'minPublishDate': min_publish_date.isoformat(),
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('minPublishDate', resp.data)

        # Re-get project
        project = Project.objects.get(pk=project.pk)
        self.assertEqual(project.min_publish_date, old_min_publish_date)

        # Clean
        if project.publish_mode != old_publish_mode:
            project.publish_mode = old_publish_mode
            project.save()


    def _response_fail_change_mode_to_review(self, project):
        resp = self.client.patch(
            reverse(self.api_change_mode_detail, kwargs={'pk': project.pk}),
            json.dumps({
                'publishMode': Project.PUBLISH_MODE_REVIEW,
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('publishMode', resp.data)
        self.assertIn('publishErrors', resp.data)

        return resp

    def test_cannot_change_to_review_for_project_not_ready_for_publish(self):
        # Project without lessons
        project = self._get_new_project_with_lessons(0)
        resp = self._response_fail_change_mode_to_review(project)
        self.assertIn('lessons', resp.data['publishErrors'])

        # Project with no ready lessons:
        project = self._get_new_project_with_lessons()
        lesson_not_ready = project.lessons.all()[0]
        lesson_not_ready.duration = 0
        lesson_not_ready.save()
        resp = self._response_fail_change_mode_to_review(project)
        self.assertIn('lessons', resp.data['publishErrors'])
        self.assertIn('duration', resp.data['publishErrors']['lessons'][lesson_not_ready.id])

        # Project with Tinkercad / Circuits lesson without steps:
        project = self._get_new_project_with_lessons()
        # add lessons that must have steps for publishing:
        lesson_apps_with_steps = [app for app,_ in Lesson.APPLICATIONS if app not in Lesson.STEPLESS_APPS]
        step_app_lessons_ids = []
        for lesson_app in lesson_apps_with_steps:
            lesson_without_steps = project.lessons.create(
                title='Lesson 101 - %s' %(lesson_app,),
                application=lesson_app,
                duration=30,
                order=0,
            )
            step_app_lessons_ids.append(lesson_without_steps.id)
        resp = self._response_fail_change_mode_to_review(project)
        self.assertIn('lessons', resp.data['publishErrors'])
        for step_app_lesson_id in step_app_lessons_ids:
            self.assertIn(step_app_lesson_id, resp.data['publishErrors']['lessons'])
            self.assertIn('stepsIds', resp.data['publishErrors']['lessons'][step_app_lesson_id])

        # Project with video lesson without a video is set:
        project = self._get_new_project_with_lessons()
        lesson_without_video = project.lessons.create(
            title='Lesson 101 - lesson without video',
            application='video',
            application_blob={'video': {}},
            duration=30,
            order=0,
        )
        resp = self._response_fail_change_mode_to_review(project)
        self.assertIn('lessons', resp.data['publishErrors'])
        self.assertIn(lesson_without_video.id, resp.data['publishErrors']['lessons'])
        self.assertIn('applicationBlob', resp.data['publishErrors']['lessons'][lesson_without_video.id])


    def test_cannot_access_change_mode_when_project_published(self):
        project = self._get_new_project_with_lessons()
        project.publish_mode = Project.PUBLISH_MODE_PUBLISHED
        project.save()

        # authenticate with super user (reviewer is super user):
        self.client.force_authenticate(self.reviewer_user)

        resp = self.client.get(
            reverse(self.api_change_mode_detail, kwargs={'pk': project.pk})
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['publishMode'], project.publish_mode)

        resp = self.client.patch(
            reverse(self.api_change_mode_detail, kwargs={'pk': project.pk}),
            json.dumps({
                'publishMode': Project.PUBLISH_MODE_READY,
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('publishMode', resp.data)

        resp = self.client.patch(
            reverse(self.api_change_mode_detail, kwargs={'pk': project.pk}),
            json.dumps({
                'publishMode': Project.PUBLISH_MODE_REVIEW,
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('publishMode', resp.data)

        resp = self.client.patch(
            reverse(self.api_change_mode_detail, kwargs={'pk': project.pk}),
            json.dumps({
                'publishMode': Project.PUBLISH_MODE_EDIT,
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('publishMode', resp.data)

    @mock.patch.object(send_mail_template.sendwithus_api, 'templates', mock_sendwithus_templates)
    @mock.patch.object(send_mail_template.sendwithus_api, 'send')
    def test_project_change_mode_ready_to_publish(self, mock_send):
        project = self._get_new_project_with_lessons()

        # Owner - edit->review

        self.client.force_authenticate(self.owner_user)
        min_publish_date = utc_now() + timedelta(days=1)
        resp = self.client.patch(
            reverse(self.api_change_mode_detail, kwargs={'pk': project.pk}),
            json.dumps({
                'publishMode': Project.PUBLISH_MODE_REVIEW,
                'minPublishDate': min_publish_date.isoformat(),
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['publishMode'], Project.PUBLISH_MODE_REVIEW)
        self.assertEqual(parse_datetime(resp.data['minPublishDate']), min_publish_date)

        project = Project.objects.get(pk=project.pk)
        self.assertEqual(project.publish_mode, Project.PUBLISH_MODE_REVIEW)
        self.assertEqual(project.min_publish_date, min_publish_date)
        self.assertIsNone(project.publish_date)

        # Reviewer - review->published (actual moves to ready for publish)

        self.client.force_authenticate(self.reviewer_user)
        resp = self.client.patch(
            reverse(self.api_change_mode_detail, kwargs={'pk': project.pk}),
            json.dumps({
                'publishMode': Project.PUBLISH_MODE_PUBLISHED,
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['publishMode'], Project.PUBLISH_MODE_READY)

        project = Project.objects.get(pk=project.pk)
        self.assertEqual(project.publish_mode, Project.PUBLISH_MODE_READY)
        self.assertIsNone(project.publish_date)

    @mock.patch.object(send_mail_template.sendwithus_api, 'templates', mock_sendwithus_templates)
    @mock.patch.object(send_mail_template.sendwithus_api, 'send')
    def test_task_publish_ready_projects(self, mock_send):
        project = self._get_new_project_with_lessons()
        project.publish_mode = Project.PUBLISH_MODE_READY
        project.min_publish_date = utc_now() - timedelta(hours=1)
        project.save()
        project.registrations.create(user=get_user_model().objects.first())

        publish_ready_projects.run()

        project = Project.objects.get(pk=project.pk)
        self.assertEqual(project.publish_mode, Project.PUBLISH_MODE_PUBLISHED)
        self.assertEqual(project.publish_date, project.updated)
        self.assertEqual(project.registrations.count(), 0)

        self._check_notifications(project, None, Project.PUBLISH_MODE_PUBLISHED, Project.PUBLISH_MODE_READY, mock_send)


    def test_owner_can_get_project_change_mode(self):
        project = self._get_new_project_with_lessons()
        project.min_publish_date = parse_datetime('2015-08-23T15:46:30Z')
        project.save()

        resp = self.client.get(
            reverse(self.api_change_mode_detail, kwargs={'pk': project.pk}),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['publishMode'], project.publish_mode)
        self.assertEqual(parse_datetime(resp.data['minPublishDate']), project.min_publish_date)

    def test_owner_change_mode(self):
        self.client.force_authenticate(self.owner_user)
        project = self._get_new_project_with_lessons()

        # From edit mode
        self._test_can_change_mode(project, self.owner_user, Project.PUBLISH_MODE_REVIEW, Project.PUBLISH_MODE_EDIT)
        self._test_cannot_change_mode(project, self.owner_user, Project.PUBLISH_MODE_READY, Project.PUBLISH_MODE_EDIT)
        self._test_cannot_change_mode(project, self.owner_user, Project.PUBLISH_MODE_PUBLISHED, Project.PUBLISH_MODE_EDIT)

        # From review mode
        self._test_cannot_change_mode(project, self.owner_user, Project.PUBLISH_MODE_EDIT, Project.PUBLISH_MODE_REVIEW)
        self._test_cannot_change_mode(project, self.owner_user, Project.PUBLISH_MODE_READY, Project.PUBLISH_MODE_REVIEW)
        self._test_cannot_change_mode(project, self.owner_user, Project.PUBLISH_MODE_PUBLISHED, Project.PUBLISH_MODE_REVIEW)

        # From ready mode
        self._test_cannot_change_mode(project, self.owner_user, Project.PUBLISH_MODE_EDIT, Project.PUBLISH_MODE_READY)
        self._test_cannot_change_mode(project, self.owner_user, Project.PUBLISH_MODE_REVIEW, Project.PUBLISH_MODE_READY)
        self._test_cannot_change_mode(project, self.owner_user, Project.PUBLISH_MODE_PUBLISHED, Project.PUBLISH_MODE_READY)

    def test_owner_can_change_min_publish_date(self):
        project = self._get_new_project_with_lessons()

        date_future = utc_now() + timedelta(hours=1)
        self._test_can_change_min_publish_date(project, self.owner_user, Project.PUBLISH_MODE_EDIT, date_future)
        self._test_can_change_min_publish_date(project, self.owner_user, Project.PUBLISH_MODE_REVIEW, date_future)
        self._test_can_change_min_publish_date(project, self.owner_user, Project.PUBLISH_MODE_READY, date_future)

        date_past = utc_now() - timedelta(hours=1)
        self._test_can_change_min_publish_date(project, self.owner_user, Project.PUBLISH_MODE_EDIT, date_past)
        self._test_can_change_min_publish_date(project, self.owner_user, Project.PUBLISH_MODE_REVIEW, date_past)
        self._test_can_change_min_publish_date(project, self.owner_user, Project.PUBLISH_MODE_READY, date_past)

        self._test_can_change_min_publish_date(project, self.owner_user, Project.PUBLISH_MODE_EDIT, None)
        self._test_can_change_min_publish_date(project, self.owner_user, Project.PUBLISH_MODE_REVIEW, None)
        self._test_can_change_min_publish_date(project, self.owner_user, Project.PUBLISH_MODE_READY, None)


    def test_reviewer_can_get_project_change_mode(self):
        self.client.force_authenticate(self.reviewer_user)

        project = self._get_new_project_with_lessons()
        project.min_publish_date = parse_datetime('2015-08-23T15:46:30Z')
        project.save()

        resp = self.client.get(
            reverse(self.api_change_mode_detail, kwargs={'pk': project.pk}),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['publishMode'], project.publish_mode)
        self.assertEqual(parse_datetime(resp.data['minPublishDate']), project.min_publish_date)

    def test_reviewer_change_mode(self):
        self.client.force_authenticate(self.reviewer_user)
        project = self._get_new_project_with_lessons()

        # Note: Operations that can be done by owner only are skipped here, since a reviewer is defined as
        #       superuser which can do whatever the owner can do.

        # From edit mode
        # self._test_cannot_change_mode(project, self.reviewer_user, Project.PUBLISH_MODE_REVIEW, Project.PUBLISH_MODE_EDIT)
        # self._test_cannot_change_mode(project, self.reviewer_user, Project.PUBLISH_MODE_READY, Project.PUBLISH_MODE_EDIT)
        # self._test_cannot_change_mode(project, self.reviewer_user, Project.PUBLISH_MODE_PUBLISHED, Project.PUBLISH_MODE_EDIT)

        # From review mode
        # self._test_cannot_change_mode(project, self.reviewer_user, Project.PUBLISH_MODE_EDIT, Project.PUBLISH_MODE_REVIEW)
        self._test_can_change_mode(project, self.reviewer_user, Project.PUBLISH_MODE_READY, Project.PUBLISH_MODE_REVIEW)
        self._test_can_change_mode(project, self.reviewer_user, Project.PUBLISH_MODE_PUBLISHED, Project.PUBLISH_MODE_REVIEW)

        # From ready mode
        # self._test_cannot_change_mode(project, self.reviewer_user, Project.PUBLISH_MODE_EDIT, Project.PUBLISH_MODE_READY)
        self._test_can_change_mode(project, self.reviewer_user, Project.PUBLISH_MODE_REVIEW, Project.PUBLISH_MODE_READY)
        self._test_cannot_change_mode(project, self.reviewer_user, Project.PUBLISH_MODE_PUBLISHED, Project.PUBLISH_MODE_READY)

    def test_reviewer_cannot_change_min_publish_date(self):
        project = self._get_new_project_with_lessons()

        # Note: Operations that can be done by owner only are skipped here, since a reviewer is defined as
        #       superuser which can do whatever the owner can do.

        # date_future = utc_now() + timedelta(hours=1)
        # self._test_cannot_change_min_publish_date(project, self.reviewer_user, Project.PUBLISH_MODE_EDIT, date_future)
        # self._test_cannot_change_min_publish_date(project, self.reviewer_user, Project.PUBLISH_MODE_REVIEW, date_future)
        # self._test_cannot_change_min_publish_date(project, self.reviewer_user, Project.PUBLISH_MODE_READY, date_future)
        #
        # date_past = utc_now() - timedelta(hours=1)
        # self._test_cannot_change_min_publish_date(project, self.reviewer_user, Project.PUBLISH_MODE_EDIT, date_past)
        # self._test_cannot_change_min_publish_date(project, self.reviewer_user, Project.PUBLISH_MODE_REVIEW, date_past)
        # self._test_cannot_change_min_publish_date(project, self.reviewer_user, Project.PUBLISH_MODE_READY, date_past)
        #
        # self._test_cannot_change_min_publish_date(project, self.reviewer_user, Project.PUBLISH_MODE_EDIT, None)
        # self._test_cannot_change_min_publish_date(project, self.reviewer_user, Project.PUBLISH_MODE_REVIEW, None)
        # self._test_cannot_change_min_publish_date(project, self.reviewer_user, Project.PUBLISH_MODE_READY, None)


    def test_reset_current_editor_when_change_publish_mode_from_edit(self):
        project = self._get_new_project_with_lessons()
        project.current_editor = self.owner_user.delegates.first()  # project edit lock by owner delegate
        project.save()

        self._test_cannot_change_mode(project, self.owner_user, Project.PUBLISH_MODE_REVIEW, Project.PUBLISH_MODE_EDIT)

        self.client.force_authenticate(self.owner_user)
        resp = self.client.patch(
            reverse(self.api_change_mode_detail, kwargs={'pk': project.pk}) + '?forceEditFrom=%s'%project.current_editor.id,
            json.dumps({
                'publishMode': Project.PUBLISH_MODE_REVIEW,
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['publishMode'], Project.PUBLISH_MODE_REVIEW)

        # Re-get project
        project = Project.objects.get(pk=project.pk)
        self.assertEqual(project.publish_mode, Project.PUBLISH_MODE_REVIEW)
        self.assertIsNone(project.current_editor)

    def test_reset_current_editor_when_project_owner_delegator_removes_editor_delegate(self):
        project = self._get_new_project_with_lessons()
        editor = self.owner_user.delegates.first()
        project.current_editor = editor  # project edit lock by owner delegate
        project.save()

        self.client.force_authenticate(self.owner_user)

        # Delete bulk

        resp = self.client.delete(
            reverse('api:my-delegates') + '?idList=%s,'%editor.id,
        )
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(self.owner_user.delegates.filter(pk=editor.pk).exists())

        # Re-get project
        project = Project.objects.get(pk=project.pk)
        self.assertIsNone(project.current_editor)

        # Delete single

        # re-add the delegate:
        OwnerDelegate.objects.create(owner=self.owner_user, user=editor)
        project.current_editor = editor  # project edit lock by owner delegate
        project.save()

        resp = self.client.delete(
            reverse('api:my-delegates-detail', kwargs={'delegate_pk': editor.pk}),
        )
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(self.owner_user.delegates.filter(pk=editor.pk).exists())

        # Re-get project
        project = Project.objects.get(pk=project.pk)
        self.assertIsNone(project.current_editor)

    def test_reset_current_editor_when_editor_delegate_removes_project_owner_delegator(self):
        project = self._get_new_project_with_lessons()
        editor = self.owner_user.delegates.first()
        project.current_editor = editor  # project edit lock by owner delegate
        project.save()

        self.client.force_authenticate(editor)

        # Delete bulk

        resp = self.client.delete(
            reverse('api:my-delegators') + '?idList=%s,'%self.owner_user.id,
        )
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(self.owner_user.delegates.filter(pk=editor.pk).exists())

        # Re-get project
        project = Project.objects.get(pk=project.pk)
        self.assertIsNone(project.current_editor)

        # Delete single

        # re-add the editor:
        OwnerDelegate.objects.create(owner=self.owner_user, user=editor)
        project.current_editor = editor  # project edit lock by owner delegate
        project.save()

        resp = self.client.delete(
            reverse('api:my-delegators-detail', kwargs={'delegator_pk': self.owner_user.pk}),
        )
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(self.owner_user.delegates.filter(pk=editor.pk).exists())

        # Re-get project
        project = Project.objects.get(pk=project.pk)
        self.assertIsNone(project.current_editor)


    @mock.patch.object(send_mail_template.sendwithus_api, 'templates', mock_sendwithus_templates)
    @mock.patch.object(send_mail_template.sendwithus_api, 'send')
    def test_send_emails_projects_in_review_summary(self, mock_send):
        staff_recipients = settings.STAFF_EMAILS
        last_items_limit = settings.PROJECTS_IN_REVIEW_SUMMARY_LAST_ITEMS_LIMIT

        # Make some projects in review mode:
        new_projects_in_review = [self._get_new_project_with_lessons(1) for i in xrange(0, last_items_limit+1)]
        for new_project in new_projects_in_review:
            new_project.publish_mode = Project.PUBLISH_MODE_REVIEW
            new_project.save()

        projects_in_review = Project.objects.filter(publish_mode=Project.PUBLISH_MODE_REVIEW)
        expected_total_projects_in_review = projects_in_review.count()
        expected_last_projects_in_review_ids = [x.id for x in projects_in_review.order_by('-updated')[:last_items_limit]]

        send_staff_emails_of_projects_in_review_summary()

        executed_emails_set = {call[1]['recipient']['address'] for call in mock_send.call_args_list}
        self.assertSetEqual(executed_emails_set, set(staff_recipients))

        first_call = mock_send.call_args_list[0] if mock_send.call_args_list else None
        if first_call:
            total_projects_in_review = first_call[1]['email_data']['projects_in_review']['total']
            last_projects_in_review_ids = [x['id'] for x in first_call[1]['email_data']['projects_in_review']['last_items']]
            self.assertEqual(total_projects_in_review, expected_total_projects_in_review)
            self.assertListEqual(last_projects_in_review_ids, expected_last_projects_in_review_ids)
            self.assertEqual(len(last_projects_in_review_ids), len(expected_last_projects_in_review_ids))

        # Cleanup
        for new_project in new_projects_in_review:
            new_project.delete()
