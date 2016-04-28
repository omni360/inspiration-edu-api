import unittest
import mock
import json
import httpretty

from httplib import HTTPResponse

from django.db.models import Count
from django.core.urlresolvers import reverse
from django.contrib.auth import get_user_model
from django.test.utils import override_settings
from django.core.serializers.json import DjangoJSONEncoder

from rest_framework.test import APITestCase as DRFTestCase

from .mock_oxygen import MockOxygen
from .base_test_case import BaseTestCase, mock_sendwithus_templates

from api.emails import joined_classroom_email
from api.tasks import send_mail_template
from api.models import ClassroomState, ChildGuardian, Classroom


@override_settings(
    CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
    CELERY_ALWAYS_EAGER=True,
    BROKER_BACKEND='memory')
class JoinedClassroomEmail(BaseTestCase, DRFTestCase):

    fixtures = ['test_projects_fixture_1.json']

    @mock.patch.object(send_mail_template.sendwithus_api, 'templates', mock_sendwithus_templates)
    @mock.patch.object(send_mail_template.sendwithus_api, 'send')
    def test_email_sent_on_join_classroom(self, mock_send):
        """Test that email is sent when a child joins a classroom"""

        joined_classroom_email(
            # Get user with moderators.
            ClassroomState.objects.exclude(user__guardians=None).first()
        )
        self.assertTrue(mock_send.called)

    @mock.patch.object(send_mail_template.sendwithus_api, 'templates', mock_sendwithus_templates)
    @mock.patch.object(send_mail_template.sendwithus_api, 'send')
    def test_email_sent_to_all_moderators(self, mock_send):
        """Email should be sent to all the moderators of the child"""

        classroom_state = ClassroomState.objects.annotate(
            moderators_count=Count('user__guardians')
        ).filter(moderators_count__gte=3).first()

        joined_classroom_email(classroom_state)

        self.assertEqual(
            mock_send.call_count,
            classroom_state.user.guardians.exclude(
                id=classroom_state.classroom.owner_id
            ).count()
        )

    @mock.patch.object(send_mail_template.sendwithus_api, 'templates', mock_sendwithus_templates)
    @mock.patch.object(send_mail_template.sendwithus_api, 'send')
    def test_email_not_sent_to_teacher_of_class(self, mock_send):
        """If the teacher of the class is a moderator of the child, email should not be sent"""
        
        classroom_state = ClassroomState.objects.exclude(
            user__guardians=None
        ).first()

        created_teacher_moderator = False
        cg = None
        teacher = classroom_state.classroom.owner
        if teacher not in classroom_state.user.guardians.all():
            cg = ChildGuardian(
                child=classroom_state.user,
                guardian=teacher,
                moderator_type=ChildGuardian.MODERATOR_EDUCATOR,
            ).save()

        joined_classroom_email(classroom_state)

        for call in mock_send.call_args_list:
            if call[1]['recipient']['address'] == teacher.email:
                self.fail('Teacher address in recipients list')

        if created_teacher_moderator:
            cg.delete()

    @mock.patch.object(send_mail_template.sendwithus_api, 'templates', mock_sendwithus_templates)
    @mock.patch.object(send_mail_template.sendwithus_api, 'send')
    def test_email_sent_for_classroom_enrollment_via_student_api(self, mock_send):
        """Make sure that the email is sent to the student for the a /classrooms/:id/students/:id/"""

        # Child with at least 2 moderators.
        child = get_user_model().objects.annotate(
            moderators_count=Count('guardians')
        ).filter(is_child=True, moderators_count__gte=2).first()

        # Classroom that the child is not enrolled to.
        classroom = Classroom.objects.exclude(
            id__in=child.classrooms.all().values_list('id', flat=True)
        ).first()

        # Log in with teacher of classroom.
        self.client.force_authenticate(classroom.owner)

        student_state_url = reverse('api:classroom-students-detail',  kwargs={
            'classroom_pk': classroom.pk,
            'pk': child.pk,
        })

        # Make sure child is not enrolled.
        resp = self.client.get(student_state_url)
        self.assertEqual(resp.status_code, 404)

        # Enroll student to classroom
        resp = self.client.put(
            student_state_url,
            json.dumps({}, cls=DjangoJSONEncoder),
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [200, 201])

        # Make sure that an email was sent to the moderators.
        self.assertTrue(mock_send.called)

    @mock.patch.object(send_mail_template.sendwithus_api, 'templates', mock_sendwithus_templates)
    @mock.patch.object(send_mail_template.sendwithus_api, 'send')
    @httpretty.activate
    def test_email_sent_for_classroom_enrollment_via_patching_my_studnets(self, mock_send):
        """Make sure that the email is sent to the student for the a PATCH to auth/me/students/:id/"""


        # Child with at least 2 moderators.
        child = get_user_model().objects.annotate(
            moderators_count=Count('guardians')
        ).filter(is_child=True, moderators_count__gte=2).first()

        # Classroom that the child is not enrolled to.
        classroom = Classroom.objects.exclude(
            id__in=child.classrooms.all().values_list('id', flat=True)
        ).first()

        mock_oxygen = MockOxygen()
        mock_oxygen.set_mock_user_as_instance(child)
        mock_oxygen.set_mock_user_as_instance(classroom.owner)
        mock_oxygen.mock_oxygen_operations(['add_moderator_children'])

        # Log in with teacher of classroom.
        self.client.force_authenticate(classroom.owner)

        my_students_url = reverse('api:my-students')

        # Create an unapproved student status.
        ClassroomState(
            classroom=classroom,
            user=child,
            status=ClassroomState.PENDING_STATUS
        ).save()

        # Enroll student to classroom
        resp = self.client.patch(
            my_students_url,
            json.dumps([{
                'id': child.pk,
                'studentClassroomStates': [{
                    'classroomId': classroom.pk,
                    'status': ClassroomState.APPROVED_STATUS,
                }],
            }], cls=DjangoJSONEncoder),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)

        # Make sure that an email was sent to the moderators.
        self.assertTrue(mock_send.called)
