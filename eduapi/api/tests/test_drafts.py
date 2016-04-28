import json
import re
import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.serializers.json import DjangoJSONEncoder
from django.core.urlresolvers import reverse
from django.db.models import Count, Q
from django.test import TestCase
from django.utils import unittest
from django.utils.timezone import now as utc_now
from django.test.utils import override_settings
from rest_framework.test import APITestCase
from api.models import Step, Lesson, Project, OwnerDelegate

from rest_framework.test import APITestCase as DRFTestCase
from .base_test_case import BaseTestCase, mock_sendwithus_templates

from api.tasks import (
    notify_and_mail_users,
    notify_user,
    send_mail_template,
)

from test_project_review_process import ProjectReviewProcessTests


class DraftsTest(TestCase):
    fixtures = ['test_projects_fixture_1.json']

    def setUp(self):
        self.published_project = Project.objects.filter(
            publish_mode=Project.PUBLISH_MODE_PUBLISHED,
            lessons__in=Lesson.objects.annotate(num_steps=Count('steps')).filter(num_steps__gt=0)
        )[0]

    def test_draft_deep_create_and_discard(self):
        # get lesson with steps:
        project = self.published_project
        lesson = project.lessons.annotate(num_steps=Count('steps')).filter(num_steps__gt=0).all()[0]
        step = lesson.steps.all()[0]
        self.assertFalse(step.has_draft)
        self.assertFalse(lesson.has_draft)
        self.assertFalse(project.has_draft)

        # create step draft:
        draft_step, _ = step.draft_get_or_create()
        self.assertTrue(draft_step.is_draft)
        self.assertTrue(step.has_draft)

        # check drafts are created also for the project and all its lessons and their steps:
        self.assertTrue(project.has_draft)
        for lesson in project.lessons.all():
            self.assertTrue(lesson.has_draft)
            for step in lesson.steps.all():
                self.assertTrue(step.has_draft)

        # check that project draft is in EDIT mode:
        self.assertEqual(project.draft_object.publish_mode, Project.PUBLISH_MODE_EDIT)

        # discard project draft:
        project.draft_discard()
        project = Project.objects.get(pk=project.pk)
        self.assertFalse(project.has_draft)
        for lesson in project.lessons.all():
            self.assertFalse(lesson.has_draft)
            for step in lesson.steps.all():
                self.assertFalse(step.has_draft)

    def test_draft_deep_apply(self):
        # get lesson with steps, and create draft for one of its steps:
        project = self.published_project
        lesson = project.lessons.annotate(num_steps=Count('steps')).filter(num_steps__gt=0).all()[0]
        step = lesson.steps.all()[0]

        # create draft for step and change title:
        draft_step, _ = step.draft_get_or_create()
        draft_step.title = 'Draft Step Title'
        draft_step.save()

        # apply project draft:
        project.draft_apply()

        # check step draft is applied:
        step = Step.objects.get(pk=step.pk)
        self.assertTrue(step.has_draft)
        self.assertEqual(step.title, draft_step.title)

    def test_draft_writable_data_fields(self):
        project = self.published_project
        draft_project, _ = project.draft_get_or_create()

        # change draft apply field:
        draft_field_description = 'The description can be set and applied on draft...'
        draft_project.description = draft_field_description

        # change draft additional update field (but not applied field):
        draft_field_current_editor = get_user_model().objects.all()[0]
        draft_project.current_editor = draft_field_current_editor
        self.assertNotEqual(draft_field_current_editor, project.current_editor)

        # change field that draft can not change:
        draft_field_owner = get_user_model().objects.filter(is_child=False).exclude(pk=project.owner.pk)[0]
        draft_project.owner = draft_field_owner
        self.assertNotEqual(draft_field_owner, project.owner)

        old_project = project

        # save draft project and check changed fields:
        draft_project.save()

        # re-get project and its draft and check data:
        project = Project.objects.get(pk=project.pk)
        self.assertEqual(project.description, old_project.description)
        self.assertEqual(project.current_editor, old_project.current_editor)
        self.assertEqual(project.owner, old_project.owner)
        draft_project = project.draft_object
        self.assertEqual(draft_project.description, draft_field_description)  #changed
        self.assertEqual(draft_project.current_editor.pk, draft_field_current_editor.pk)  #changed
        self.assertEqual(draft_project.owner.pk, project.owner.pk)  #not changed!
        self.assertSequenceEqual(
            set(project.draft_diff_fields()),
            {'description'}
        )

        # apply draft project and check saved fields:
        project.draft_apply()

        # re-get project and its draft and check data saved:
        project = Project.objects.get(pk=project.pk)
        self.assertTrue(project.has_draft)
        self.assertEqual(project.description, draft_field_description)  #applied
        self.assertNotEqual(project.current_editor, draft_field_current_editor)  #not applied!
        self.assertNotEqual(project.owner, draft_field_owner)  #not applied!


@override_settings(
    STAFF_EMAILS=['a@test.com2', 'b@test.com2'],
    PROJECTS_IN_REVIEW_SUMMARY_LAST_ITEMS_LIMIT=3,
)
# class ObjectCopyApiTests(ProjectReviewProcessTests):
class ObjectCopyApiTests(BaseTestCase, DRFTestCase):

    fixtures = ['test_projects_fixture_1.json']

    def setUp(self, *args, **kwargs):
        super(ObjectCopyApiTests, self).setUp(*args, **kwargs)

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

        self.published_project = self._make_project_with_lessons_and_steps(owner=self.owner_user)
        self.published_project_with_draft = self._make_project_with_lessons_and_steps(owner=self.owner_user)

        self.unpublished_project = self._make_project_with_lessons_and_steps(owner=self.owner_user)
        self.unpublished_project.publish_mode = Project.PUBLISH_MODE_EDIT
        self.unpublished_project.publish_date = None
        self.unpublished_project.save()

        self.api_draft_detail = 'api:project-draft-detail'
        self.api_draft_change_mode_detail = 'api:project-draft-detail'

        #make published project with draft:
        self.published_project_with_draft.draft_get_or_create()

        self.client.force_authenticate(self.owner_user)


    def _make_project_with_lessons_and_steps(self, num_lessons=2, num_steps=3, owner=None):
        owner = owner or self.owner_user
        project = Project.objects.create(
            owner=owner,
            title='Testing 101',
            publish_mode=Project.PUBLISH_MODE_PUBLISHED,
            publish_date=utc_now(),
            description='Learn how to test Django applications using Python\'s unittest',
            duration=45,
            banner_image='http://placekitten.com/2048/640/',
            card_image='http://placekitten.com/1024/768/',
            age=Project.AGES[0][0],
            difficulty=Project.DIFFICULTIES[0][0],
            license=Project.LICENSES[0][0],
            tags='3D-Design Tools,Printing',
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

        for x in range(num_lessons):
            lesson = Lesson.objects.create(
                project=project,
                title='Lesson 10%s' % (x,),
                application='tinkercad',
                duration=30,
            )
            for y in range(num_steps):
                step = Step.objects.create(
                    lesson=lesson,
                    title='Step of lesson - %s' % (y,),
                    description='Move to the next step...',
                )
        return project


    def test_owner_or_delegator_can_get_create_delete_draft(self):
        project = self.published_project
        project_draft_api_detail = reverse(self.api_draft_detail, kwargs={'project_pk': project.pk})

        owners = [self.owner_user] + list(self.owner_user.delegates.filter(is_child=False))
        for owner in owners:
            self.client.force_authenticate(owner)
            project = Project.objects.get(pk=project.pk)  #refresh project

            # no draft -> 404
            resp = self.client.get(project_draft_api_detail)
            self.assertEqual(resp.status_code, 404)

            # create draft:
            draft_changes = {
                'title': 'DRAFT:' + project.title,
                'description': 'DRAFT:' + project.description,
                'tags': 'DRAFT',
                'cardImage': 'https://draft.com/draft_img.jpg',
            }
            expected_origin_changes = {k: getattr(project, re.sub(r'[A-Z]', lambda m: '_'+m.group(0).lower(), k)) for k in draft_changes.keys()}
            resp = self.client.patch(
                project_draft_api_detail,
                data=json.dumps(draft_changes, cls=DjangoJSONEncoder),
                content_type='application/json'
            )
            self.assertEqual(resp.status_code, 200)
            self.assertIn('origin', resp.data)
            self.assertDictEqual(resp.data['origin']['diff'], expected_origin_changes)
            self.assertEqual(resp.data['origin']['publishMode'], Project.PUBLISH_MODE_PUBLISHED)

            # get draft:
            resp1 = self.client.get(project_draft_api_detail)
            self.assertEqual(resp1.status_code, 200)
            self.assertEqual(resp1.data['id'], project.draft_object.id)
            self.assertIn('origin', resp1.data)
            self.assertDictEqual(resp1.data['origin']['diff'], expected_origin_changes)

            # get project with embed=draft:
            resp2 = self.client.get(reverse('api:project-detail', kwargs={'pk': project.pk}), {'embed': 'draft'})
            self.assertEqual(resp2.status_code, 200)
            self.assertDictEqual(resp2.data['draft']['diff'], draft_changes)

            # delete the draft:
            resp = self.client.delete(project_draft_api_detail)
            self.assertEqual(resp.status_code, 204)

        # make sure that regular users can not access the draft endpoint:
        regular_user = get_user_model().objects.filter(is_child=False, is_superuser=False).exclude(pk__in=[x.id for x in owners])[0]
        self.client.force_authenticate(regular_user)
        resp = self.client.get(project_draft_api_detail)
        self.assertEqual(resp.status_code, 403)

    def test_project_diff_teacher_info(self):
        """Tests that sub-serializer teacherInfo is properly saved on draft, and origin/draft diff is properly made"""

        project = self.published_project
        self.client.force_authenticate(self.owner_user)
        project_draft_api_detail = reverse(self.api_draft_detail, kwargs={'project_pk': project.pk})

        # no draft -> 404
        resp = self.client.get(project_draft_api_detail)
        self.assertEqual(resp.status_code, 404)

        # create draft:
        draft_changes = {
            'bannerImage': 'https://draft.com/draft_img.jpg',
            'teacherInfo': {
                'grades': ['K', '1', '2', '3', '4', '5', '6'],
                'fourCS': {
                    'creativity': '<p>Creativity information</p>',
                    'critical': '<p>Critical information</p>',
                },
            },
        }
        expected_origin_changes = {
            'bannerImage': project.banner_image,
            'teacherInfo': {
                'grades': project.grades_range,
                'fourCS': {
                    'creativity': project.four_cs_creativity,
                    'critical': project.four_cs_critical,
                }
            }
        }
        expected_draft_changes = {
            'bannerImage': draft_changes['bannerImage'],
            'teacherInfo': {
                'grades': draft_changes['teacherInfo']['grades'],
                'fourCS': {
                    'creativity': draft_changes['teacherInfo']['fourCS']['creativity'],
                    'critical': draft_changes['teacherInfo']['fourCS']['critical'],
                }
            }
        }
        resp = self.client.patch(
            project_draft_api_detail,
            data=json.dumps(draft_changes, cls=DjangoJSONEncoder),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('origin', resp.data)
        self.assertDictEqual(resp.data['origin']['diff'], expected_origin_changes)
        self.assertEqual(resp.data['origin']['publishMode'], Project.PUBLISH_MODE_PUBLISHED)

        # get draft:
        resp1 = self.client.get(project_draft_api_detail)
        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(resp1.data['id'], project.draft_object.id)
        self.assertIn('origin', resp1.data)
        self.assertDictEqual(resp1.data['origin']['diff'], expected_origin_changes)

        # get project with embed=draft:
        resp2 = self.client.get(reverse('api:project-detail', kwargs={'pk': project.pk}), {'embed': 'draft'})
        self.assertEqual(resp2.status_code, 200)
        self.assertDictEqual(resp2.data['draft']['diff'], expected_draft_changes)

        # delete the draft:
        resp = self.client.delete(project_draft_api_detail)
        self.assertEqual(resp.status_code, 204)

    def test_project_diff_teacher_info_with_non_editable_draft_field(self):
        """Tests that non-editable draft field is not changed in sub-serializer teacherInfo"""

        # Remove 'four_cs_creativity' from Project draft apply fields:
        # IMPORTANT: Make sure to recover draft_writable_data_fields before exiting test!
        original_project_draft_writable_data_fields = Project.draft_writable_data_fields
        Project.draft_writable_data_fields.remove('four_cs_creativity')

        try:
            # get project using MyProject model:
            project = Project.objects.get(pk=self.published_project.pk)
            self.client.force_authenticate(self.owner_user)
            project_draft_api_detail = reverse(self.api_draft_detail, kwargs={'project_pk': project.pk})

            # create draft:
            draft_changes = {
                'bannerImage': 'https://draft.com/draft_img.jpg',
                'teacherInfo': {
                    'grades': ['K', '1', '2', '3', '4', '5', '6'],
                    'fourCS': {
                        'creativity': '<p>Creativity information</p>',
                        'critical': '<p>Critical information</p>',
                    },
                },
            }
            expected_origin_changes = {
                'bannerImage': project.banner_image,
                'teacherInfo': {
                    'grades': project.grades_range,
                    'fourCS': {
                        # 'creativity': project.four_cs_creativity,
                        'critical': project.four_cs_critical,
                    }
                }
            }
            expected_draft_changes = {
                'bannerImage': draft_changes['bannerImage'],
                'teacherInfo': {
                    'grades': draft_changes['teacherInfo']['grades'],
                    'fourCS': {
                        # 'creativity': draft_changes['teacherInfo']['fourCS']['creativity'],
                        'critical': draft_changes['teacherInfo']['fourCS']['critical'],
                    }
                }
            }
            resp = self.client.patch(
                project_draft_api_detail,
                data=json.dumps(draft_changes, cls=DjangoJSONEncoder),
                content_type='application/json'
            )
            self.assertEqual(resp.status_code, 200)
            self.assertIn('origin', resp.data)
            self.assertDictEqual(resp.data['origin']['diff'], expected_origin_changes)
            self.assertEqual(resp.data['origin']['publishMode'], Project.PUBLISH_MODE_PUBLISHED)

            # get draft:
            resp1 = self.client.get(project_draft_api_detail)
            self.assertEqual(resp1.status_code, 200)
            self.assertEqual(resp1.data['id'], project.draft_object.id)
            self.assertIn('origin', resp1.data)
            self.assertDictEqual(resp1.data['origin']['diff'], expected_origin_changes)

            # get project with embed=draft:
            resp2 = self.client.get(reverse('api:project-detail', kwargs={'pk': project.pk}), {'embed': 'draft'})
            self.assertEqual(resp2.status_code, 200)
            self.assertDictEqual(resp2.data['draft']['diff'], expected_draft_changes)

            # delete the draft:
            resp = self.client.delete(project_draft_api_detail)
            self.assertEqual(resp.status_code, 204)
        finally:
            # Recover Project:
            Project.draft_writable_data_fields = original_project_draft_writable_data_fields

    def test_can_create_draft_only_for_published_project(self):
        project = self.unpublished_project
        project_draft_api_detail = reverse(self.api_draft_detail, kwargs={'project_pk': project.pk})

        resp = self.client.get(project_draft_api_detail)
        self.assertEqual(resp.status_code, 404)

        resp = self.client.patch(project_draft_api_detail, {}, content_type='application/json')
        self.assertEqual(resp.status_code, 404)


    def _check_draft_notifications(self, project, user, to_mode, from_mode, mock_send):
        # Check notifications:
        project_owner_and_delegates_qs = get_user_model().objects.filter(Q(pk=project.owner.pk) | Q(pk__in=project.owner.delegates.all()))
        for delegate in project_owner_and_delegates_qs:
            notification = delegate.notifications.filter(
                verb__in=['project_draft_mode_changed_by_target','project_draft_mode_changed_by_target_with_feedback'],
                actor_content_type__model=Project._meta.model_name,
                actor_object_id=project.pk,
            ).order_by(
                '-timestamp'
            ).first()
            self.assertEqual(notification.target, user)
            self.assertEqual(notification.data['publishMode'], Project.PUBLISH_MODE_PUBLISHED)
            self.assertEqual(notification.data['publishDate'], project.publish_date.strftime('%Y-%m-%d %H:%M'))
            self.assertEqual(notification.data['draftPublishMode'], to_mode)
            self.assertEqual(notification.data['draftOldPublishMode'], from_mode)
            self.assertIn('draftDiff', notification.data)
            if to_mode == Project.PUBLISH_MODE_PUBLISHED:
                self.assertEqual(notification.data['draftAppliedDate'], project.updated.strftime('%Y-%m-%d %H:%M'))

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
    def _test_draft_can_change_mode(self, project, user, to_mode, from_mode, mock_send):
        project = Project.objects.get(pk=project.pk)  #reload project
        project_draft = project.draft_get()

        if user:
            self.client.force_authenticate(user)

        old_publish_mode = project_draft.publish_mode
        if from_mode:
            project_draft.publish_mode = from_mode
            project_draft.save()

        resp = self.client.patch(
            reverse(self.api_draft_change_mode_detail, kwargs={'project_pk': project.pk}),
            json.dumps({
                'publishMode': to_mode,
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        if to_mode == Project.PUBLISH_MODE_READY:
            to_mode = Project.PUBLISH_MODE_PUBLISHED
        self.assertEqual(resp.data['publishMode'], to_mode)

        self._check_draft_notifications(project, user, to_mode, from_mode, mock_send)

        # Re-get project
        project = Project.objects.get(pk=project.pk)
        new_project_draft = project.draft_get()
        if to_mode == Project.PUBLISH_MODE_PUBLISHED:
            self.assertIsNone(new_project_draft)
        else:
            self.assertEqual(new_project_draft.publish_mode, to_mode)

        # Clean
        if new_project_draft is None:
            project_draft, _ = project.draft_get_or_create()
        project_draft.publish_mode = old_publish_mode
        project_draft.save()

    @mock.patch.object(send_mail_template.sendwithus_api, 'templates', mock_sendwithus_templates)
    @mock.patch.object(send_mail_template.sendwithus_api, 'send')
    def _test_draft_cannot_change_mode(self, project, user, to_mode, from_mode, mock_send):
        project = Project.objects.get(pk=project.pk)  #reload project
        project_draft = project.draft_get()

        if user:
            self.client.force_authenticate(user)

        old_publish_mode = project_draft.publish_mode
        if from_mode:
            project_draft.publish_mode = from_mode
            project_draft.save()

        resp = self.client.patch(
            reverse(self.api_draft_change_mode_detail, kwargs={'project_pk': project.pk}),
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
        new_project_draft = project.draft_get()
        self.assertEqual(new_project_draft.publish_mode, from_mode)

    @mock.patch.object(send_mail_template.sendwithus_api, 'templates', mock_sendwithus_templates)
    @mock.patch.object(send_mail_template.sendwithus_api, 'send')
    def test_project_draft_change_mode_to_publish_apply(self, mock_send):
        project = self.published_project_with_draft

        self.client.force_authenticate(self.owner_user)

        # Owner - edit draft

        draft_changes = {
            'title': 'DRAFT:' + project.title,
            'description': 'DRAFT:' + project.description,
            'tags': 'DRAFT',
            'cardImage': 'https://draft.com/draft_img.jpg',
        }
        expected_origin_changes = {k: getattr(project, re.sub(r'[A-Z]', lambda m: '_'+m.group(0).lower(), k)) for k in draft_changes.keys()}
        resp = self.client.patch(
            reverse(self.api_draft_detail, kwargs={'project_pk': project.pk}),
            json.dumps(draft_changes, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('origin', resp.data)
        self.assertDictEqual(resp.data['origin']['diff'], expected_origin_changes)

        # Owner - edit->review
        resp = self.client.patch(
            reverse(self.api_draft_change_mode_detail, kwargs={'project_pk': project.pk}),
            json.dumps({
                'publishMode': Project.PUBLISH_MODE_REVIEW,
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['publishMode'], Project.PUBLISH_MODE_REVIEW)

        project = Project.objects.get(pk=project.pk)
        project_draft = project.draft_get()
        self.assertEqual(project_draft.publish_mode, Project.PUBLISH_MODE_REVIEW)

        # Reviewer - review->published (actual moves to ready for publish)

        self.client.force_authenticate(self.reviewer_user)
        resp = self.client.patch(
            reverse(self.api_draft_change_mode_detail, kwargs={'project_pk': project.pk}),
            json.dumps({
                'publishMode': Project.PUBLISH_MODE_PUBLISHED,
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['publishMode'], Project.PUBLISH_MODE_PUBLISHED)

        project = Project.objects.get(pk=project.pk)
        project_draft = project.draft_get()
        self.assertIsNone(project_draft)
        for draft_change_key, draft_change_val in draft_changes.items():
            self.assertEqual(getattr(project, re.sub(r'[A-Z]', lambda m: '_'+m.group(0).lower(), draft_change_key)), draft_change_val)

    def test_owner_change_mode(self):
        self.client.force_authenticate(self.owner_user)
        project = self.published_project_with_draft

        # From edit mode
        self._test_draft_can_change_mode(project, self.owner_user, Project.PUBLISH_MODE_REVIEW, Project.PUBLISH_MODE_EDIT)
        self._test_draft_cannot_change_mode(project, self.owner_user, Project.PUBLISH_MODE_PUBLISHED, Project.PUBLISH_MODE_EDIT)

        # From review mode
        self._test_draft_cannot_change_mode(project, self.owner_user, Project.PUBLISH_MODE_EDIT, Project.PUBLISH_MODE_REVIEW)
        self._test_draft_cannot_change_mode(project, self.owner_user, Project.PUBLISH_MODE_PUBLISHED, Project.PUBLISH_MODE_REVIEW)

    def test_reviewer_can_get_project_change_mode(self):
        project = self.published_project_with_draft
        project_draft = project.draft_get()
        self.client.force_authenticate(self.reviewer_user)

        resp = self.client.get(
            reverse(self.api_draft_change_mode_detail, kwargs={'project_pk': project.pk}),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['publishMode'], project_draft.publish_mode)

    def test_reviewer_change_mode(self):
        self.client.force_authenticate(self.reviewer_user)
        project = self.published_project_with_draft

        # Note: Operations that can be done by owner only are skipped here, since a reviewer is defined as
        #       superuser which can do whatever the owner can do.

        # From edit mode
        # self._test_draft_cannot_change_mode(project, self.reviewer_user, Project.PUBLISH_MODE_REVIEW, Project.PUBLISH_MODE_EDIT)
        # self._test_draft_cannot_change_mode(project, self.reviewer_user, Project.PUBLISH_MODE_READY, Project.PUBLISH_MODE_EDIT)
        # self._test_draft_cannot_change_mode(project, self.reviewer_user, Project.PUBLISH_MODE_PUBLISHED, Project.PUBLISH_MODE_EDIT)

        # From review mode
        # self._test_draft_cannot_change_mode(project, self.reviewer_user, Project.PUBLISH_MODE_EDIT, Project.PUBLISH_MODE_REVIEW)
        self._test_draft_can_change_mode(project, self.reviewer_user, Project.PUBLISH_MODE_READY, Project.PUBLISH_MODE_REVIEW)
        self._test_draft_can_change_mode(project, self.reviewer_user, Project.PUBLISH_MODE_PUBLISHED, Project.PUBLISH_MODE_REVIEW)

    def test_draft_reset_current_editor_when_change_publish_mode_from_edit(self):
        project = self.published_project_with_draft
        project_draft = project.draft_get()
        project_draft.current_editor = self.owner_user.delegates.first()  # project draft edit lock by owner delegate
        project_draft.save()

        self._test_draft_cannot_change_mode(project, self.owner_user, Project.PUBLISH_MODE_REVIEW, Project.PUBLISH_MODE_EDIT)
        self.client.force_authenticate(self.owner_user)
        resp = self.client.patch(
            reverse(self.api_draft_change_mode_detail, kwargs={'project_pk': project.pk}) + '?forceEditFrom=%s'%project_draft.current_editor.id,
            json.dumps({
                'publishMode': Project.PUBLISH_MODE_REVIEW,
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['publishMode'], Project.PUBLISH_MODE_REVIEW)

        # Re-get project
        project = Project.objects.get(pk=project.pk)
        project_draft = project.draft_get()
        self.assertEqual(project_draft.publish_mode, Project.PUBLISH_MODE_REVIEW)
        self.assertIsNone(project_draft.current_editor)

    def test_draft_reset_current_editor_when_project_owner_delegator_removes_editor_delegate(self):
        project = self.published_project_with_draft
        project_draft = project.draft_get()
        editor = self.owner_user.delegates.first()
        project_draft.current_editor = editor  # project draft edit lock by owner delegate
        project_draft.save()

        self.client.force_authenticate(self.owner_user)

        # Delete bulk

        resp = self.client.delete(
            reverse('api:my-delegates') + '?idList=%s,'%editor.id,
        )
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(self.owner_user.delegates.filter(pk=editor.pk).exists())

        # Re-get project
        project = Project.objects.get(pk=project.pk)
        project_draft = project.draft_get()
        self.assertIsNone(project_draft.current_editor)

        # Delete single

        # re-add the delegate:
        OwnerDelegate.objects.create(owner=self.owner_user, user=editor)
        project_draft.current_editor = editor  # project draft edit lock by owner delegate
        project_draft.save()

        resp = self.client.delete(
            reverse('api:my-delegates-detail', kwargs={'delegate_pk': editor.pk}),
        )
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(self.owner_user.delegates.filter(pk=editor.pk).exists())

        # Re-get project
        project = Project.objects.get(pk=project.pk)
        project_draft = project.draft_get()
        self.assertIsNone(project_draft.current_editor)

    def test_draft_reset_current_editor_when_editor_delegate_removes_project_owner_delegator(self):
        project = self.published_project_with_draft
        project_draft = project.draft_get()
        editor = self.owner_user.delegates.first()
        project_draft.current_editor = editor  # project draft edit lock by owner delegate
        project_draft.save()

        self.client.force_authenticate(editor)

        # Delete bulk

        resp = self.client.delete(
            reverse('api:my-delegators') + '?idList=%s,'%self.owner_user.id,
        )
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(self.owner_user.delegates.filter(pk=editor.pk).exists())

        # Re-get project
        project = Project.objects.get(pk=project.pk)
        project_draft = project.draft_get()
        self.assertIsNone(project_draft.current_editor)

        # Delete single

        # re-add the editor:
        OwnerDelegate.objects.create(owner=self.owner_user, user=editor)
        project_draft.current_editor = editor  # project draft edit lock by owner delegate
        project_draft.save()

        resp = self.client.delete(
            reverse('api:my-delegators-detail', kwargs={'delegator_pk': self.owner_user.pk}),
        )
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(self.owner_user.delegates.filter(pk=editor.pk).exists())

        # Re-get project
        project = Project.objects.get(pk=project.pk)
        project_draft = project.draft_get()
        self.assertIsNone(project_draft.current_editor)
