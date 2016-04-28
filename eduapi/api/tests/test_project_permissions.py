from collections import namedtuple
import json
import mock

from django.db.models import Count
from django.contrib.auth import get_user_model
from django.core.urlresolvers import reverse
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.auth.models import AnonymousUser

from rest_framework.test import APITestCase as DRFTestCase

from .base_test_case import BaseTestCase

from marketplace.models import Purchase
from api.models import Project, Classroom, OwnerDelegate, Group
from api.serializers import LessonSerializer, StepSerializer, ClassroomSerializer
from api.views import ProjectAndLessonPermission


class ProjectPermissionsTests(BaseTestCase, DRFTestCase):
    
    fixtures = ['test_project_permissions_fixture.json']

    def setUp(self):
        super(ProjectPermissionsTests, self).setUp()

        self.locked_project = Project.objects.exclude(lock=Project.NO_LOCK).first()

        self.regular_project = Project.objects.filter(lock=Project.NO_LOCK).first()

        self.step = self.locked_project.lessons.all().annotate(
            steps_num=Count('steps')
        ).filter(steps_num__gte=1).first().steps.first()
        if not self.step:
            raise Exception('No lesson with steps found for locked project')

        self.regular_user = get_user_model().objects.exclude(
            id__in=[self.locked_project.owner_id, self.regular_project.owner_id]
        ).exclude(
            id__in=Purchase.objects.all().values_list('user_id', flat=True)
        ).filter(
            is_superuser=False,
            is_child=False,
        ).first()

    # Test Project.check_permission_PERM
    # ##################################

    def test_permission_edit_hierarchy(self):

        user = self.locked_project.owner
        self.client.force_authenticate(user)

        old_publish_mode = self.locked_project.publish_mode
        self.locked_project.publish_mode = Project.PUBLISH_MODE_EDIT
        self.locked_project.save()

        self.assertTrue(self.locked_project.can_edit(user))
        self.assertTrue(self.locked_project.can_view(user))
        self.assertTrue(self.locked_project.can_preview(user))

        self.assertFalse(self.locked_project.can_teach(user))

        # Cleanup
        self.locked_project.publish_mode = old_publish_mode
        self.locked_project.save()

    def test_permission_teach_hierarchy(self):

        user = self.locked_project.owner
        self.client.force_authenticate(user)

        self.assertTrue(self.locked_project.can_teach(user))
        self.assertTrue(self.locked_project.can_view(user))
        self.assertTrue(self.locked_project.can_preview(user))

        self.assertFalse(self.locked_project.can_edit(user))

    def test_permission_view_hierarchy(self):

        user = self.regular_user
        user.is_child = True
        user.save()
        self.client.force_authenticate(user)

        self.assertTrue(self.regular_project.can_view(user))
        self.assertTrue(self.regular_project.can_preview(user))

        self.assertFalse(self.regular_project.can_edit(user))
        self.assertFalse(self.regular_project.can_teach(user))

        # Cleanup
        user.is_child = False
        user.save()

    def test_permission_preview_hierarchy(self):

        user = self.regular_user
        self.client.force_authenticate(user)

        self.assertTrue(self.locked_project.can_preview(user))

        self.assertFalse(self.locked_project.can_edit(user))
        self.assertFalse(self.locked_project.can_teach(user))
        self.assertFalse(self.locked_project.can_view(user))


    def test_permissions_for_owner_on_project_in_edit_mode(self):

        old_publish_mode = self.locked_project.publish_mode
        self.locked_project.publish_mode = Project.PUBLISH_MODE_EDIT
        self.locked_project.save()

        project = self.locked_project
        user = project.owner

        self.assertTrue(project.can_edit(user))
        self.assertFalse(project.can_teach(user))
        self.assertTrue(project.can_view(user))
        self.assertTrue(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        self.assertFalse(project.can_publish(user))

        # Cleanup
        self.locked_project.publish_mode = old_publish_mode
        self.locked_project.save()

    def test_permissions_for_owner_on_project_in_review_mode(self):

        old_publish_mode = self.locked_project.publish_mode
        self.locked_project.publish_mode = Project.PUBLISH_MODE_REVIEW
        self.locked_project.save()

        project = self.locked_project
        user = project.owner

        self.assertFalse(project.can_edit(user))
        self.assertFalse(project.can_teach(user))
        self.assertTrue(project.can_view(user))
        self.assertTrue(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        # self.assertFalse(project.can_publish(user))

        # Cleanup
        self.locked_project.publish_mode = old_publish_mode
        self.locked_project.save()

    def test_permissions_for_owner_on_project_in_ready_mode(self):

        old_publish_mode = self.locked_project.publish_mode
        self.locked_project.publish_mode = Project.PUBLISH_MODE_READY
        self.locked_project.save()

        project = self.locked_project
        user = project.owner

        self.assertFalse(project.can_edit(user))
        self.assertTrue(project.can_teach(user))
        self.assertTrue(project.can_view(user))
        self.assertTrue(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        # self.assertFalse(project.can_publish(user))

        # Cleanup
        self.locked_project.publish_mode = old_publish_mode
        self.locked_project.save()

    def test_permissions_for_owner_on_project_in_published_mode(self):

        old_publish_mode = self.locked_project.publish_mode
        self.locked_project.publish_mode = Project.PUBLISH_MODE_PUBLISHED
        self.locked_project.save()

        project = self.locked_project
        user = project.owner

        self.assertFalse(project.can_edit(user))
        self.assertTrue(project.can_teach(user))
        self.assertTrue(project.can_view(user))
        self.assertTrue(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        self.assertFalse(project.can_publish(user))

        # Cleanup
        self.locked_project.publish_mode = old_publish_mode
        self.locked_project.save()

    def test_permissions_for_owner_delegate_on_project_in_edit_mode(self):

        old_publish_mode = self.locked_project.publish_mode
        self.locked_project.publish_mode = Project.PUBLISH_MODE_EDIT
        self.locked_project.save()

        regular_user_delegate = OwnerDelegate.objects.create(owner=self.locked_project.owner, user=self.regular_user)

        project = self.locked_project
        user = self.regular_user

        self.assertTrue(project.can_edit(user))
        self.assertFalse(project.can_teach(user))
        self.assertTrue(project.can_view(user))
        self.assertTrue(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        self.assertFalse(project.can_publish(user))

        # Cleanup
        self.locked_project.publish_mode = old_publish_mode
        self.locked_project.save()
        regular_user_delegate.delete()

    def test_permissions_for_owner_delegate_on_project_in_review_mode(self):

        old_publish_mode = self.locked_project.publish_mode
        self.locked_project.publish_mode = Project.PUBLISH_MODE_REVIEW
        self.locked_project.save()

        regular_user_delegate = OwnerDelegate.objects.create(owner=self.locked_project.owner, user=self.regular_user)

        project = self.locked_project
        user = self.regular_user

        self.assertFalse(project.can_edit(user))
        self.assertFalse(project.can_teach(user))
        self.assertTrue(project.can_view(user))
        self.assertTrue(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        # self.assertFalse(project.can_publish(user))

        # Cleanup
        self.locked_project.publish_mode = old_publish_mode
        self.locked_project.save()
        regular_user_delegate.delete()

    def test_permissions_for_owner_delegate_on_project_in_ready_mode(self):

        old_publish_mode = self.locked_project.publish_mode
        self.locked_project.publish_mode = Project.PUBLISH_MODE_READY
        self.locked_project.save()

        regular_user_delegate = OwnerDelegate.objects.create(owner=self.locked_project.owner, user=self.regular_user)

        project = self.locked_project
        user = self.regular_user

        self.assertFalse(project.can_edit(user))
        self.assertTrue(project.can_teach(user))
        self.assertTrue(project.can_view(user))
        self.assertTrue(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        # self.assertFalse(project.can_publish(user))

        # Cleanup
        self.locked_project.publish_mode = old_publish_mode
        self.locked_project.save()
        regular_user_delegate.delete()

    def test_permissions_for_owner_delegate_on_project_in_published_mode(self):

        old_publish_mode = self.locked_project.publish_mode
        self.locked_project.publish_mode = Project.PUBLISH_MODE_PUBLISHED
        self.locked_project.save()

        regular_user_delegate = OwnerDelegate.objects.create(owner=self.locked_project.owner, user=self.regular_user)

        project = self.locked_project
        user = self.regular_user

        self.assertFalse(project.can_edit(user))
        self.assertTrue(project.can_teach(user))
        self.assertTrue(project.can_view(user))
        self.assertTrue(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        self.assertFalse(project.can_publish(user))

        # Cleanup
        self.locked_project.publish_mode = old_publish_mode
        self.locked_project.save()
        regular_user_delegate.delete()

    def test_permissions_for_superuser_on_project_in_edit_mode(self):

        old_publish_mode = self.locked_project.publish_mode
        self.locked_project.publish_mode = Project.PUBLISH_MODE_EDIT
        self.locked_project.save()

        project = self.locked_project
        user = self.regular_user
        user.is_superuser = True
        user.save()

        self.assertTrue(project.can_edit(user))
        self.assertFalse(project.can_teach(user))
        self.assertTrue(project.can_view(user))
        self.assertTrue(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        self.assertFalse(project.can_publish(user))

        # Cleanup
        self.locked_project.publish_mode = old_publish_mode
        self.locked_project.save()
        user.is_superuser = False
        user.save()

    def test_permissions_for_superuser_on_project_in_review_mode(self):

        old_publish_mode = self.locked_project.publish_mode
        self.locked_project.publish_mode = Project.PUBLISH_MODE_REVIEW
        self.locked_project.save()

        project = self.locked_project
        user = self.regular_user
        user.is_superuser = True
        user.save()

        self.assertFalse(project.can_edit(user))
        self.assertFalse(project.can_teach(user))
        self.assertTrue(project.can_view(user))
        self.assertTrue(project.can_preview(user))
        self.assertTrue(project.can_reedit(user))
        # self.assertFalse(project.can_publish(user))

        # Cleanup
        self.locked_project.publish_mode = old_publish_mode
        self.locked_project.save()
        user.is_superuser = False
        user.save()

    def test_permissions_for_superuser_on_project_in_ready_mode(self):

        old_publish_mode = self.locked_project.publish_mode
        self.locked_project.publish_mode = Project.PUBLISH_MODE_READY
        self.locked_project.save()

        project = self.locked_project
        user = self.regular_user
        user.is_superuser = True
        user.save()

        self.assertFalse(project.can_edit(user))
        self.assertTrue(project.can_teach(user))
        self.assertTrue(project.can_view(user))
        self.assertTrue(project.can_preview(user))
        self.assertTrue(project.can_reedit(user))
        # self.assertFalse(project.can_publish(user))

        # Cleanup
        self.locked_project.publish_mode = old_publish_mode
        self.locked_project.save()
        user.is_superuser = False
        user.save()

    def test_permissions_for_superuser_on_project_in_published_mode(self):

        old_publish_mode = self.locked_project.publish_mode
        self.locked_project.publish_mode = Project.PUBLISH_MODE_PUBLISHED
        self.locked_project.save()

        project = self.locked_project
        user = self.regular_user
        user.is_superuser = True
        user.save()

        self.assertFalse(project.can_edit(user))
        self.assertTrue(project.can_teach(user))
        self.assertTrue(project.can_view(user))
        self.assertTrue(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        self.assertFalse(project.can_publish(user))

        # Cleanup
        self.locked_project.publish_mode = old_publish_mode
        self.locked_project.save()
        user.is_superuser = False
        user.save()

    def test_permissions_for_application_user_on_project_in_edit_mode(self):

        old_publish_mode = self.locked_project.publish_mode
        self.locked_project.publish_mode = Project.PUBLISH_MODE_EDIT
        self.locked_project.save()

        project = self.locked_project
        user = self.regular_user
        circuits_group = Group.objects.get(name='123dcircuits')
        user.groups.add(circuits_group)

        self.assertFalse(project.can_edit(user))
        self.assertFalse(project.can_teach(user))
        self.assertTrue(project.can_view(user))
        self.assertTrue(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        self.assertFalse(project.can_publish(user))

        # Cleanup
        self.locked_project.publish_mode = old_publish_mode
        self.locked_project.save()
        user.groups.remove(circuits_group)

    def test_permissions_for_application_user_on_project_in_review_mode(self):

        old_publish_mode = self.locked_project.publish_mode
        self.locked_project.publish_mode = Project.PUBLISH_MODE_REVIEW
        self.locked_project.save()

        project = self.locked_project
        user = self.regular_user
        circuits_group = Group.objects.get(name='123dcircuits')
        user.groups.add(circuits_group)

        self.assertFalse(project.can_edit(user))
        self.assertFalse(project.can_teach(user))
        self.assertTrue(project.can_view(user))
        self.assertTrue(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        self.assertFalse(project.can_publish(user))

        # Cleanup
        self.locked_project.publish_mode = old_publish_mode
        self.locked_project.save()
        user.groups.remove(circuits_group)

    def test_permissions_for_application_user_on_project_in_ready_mode(self):

        old_publish_mode = self.locked_project.publish_mode
        self.locked_project.publish_mode = Project.PUBLISH_MODE_READY
        self.locked_project.save()

        project = self.locked_project
        user = self.regular_user
        circuits_group = Group.objects.get(name='123dcircuits')
        user.groups.add(circuits_group)

        self.assertFalse(project.can_edit(user))
        self.assertFalse(project.can_teach(user))
        self.assertTrue(project.can_view(user))
        self.assertTrue(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        self.assertFalse(project.can_publish(user))

        # Cleanup
        self.locked_project.publish_mode = old_publish_mode
        self.locked_project.save()
        user.groups.remove(circuits_group)

    def test_permissions_for_application_user_on_project_in_published_mode(self):

        old_publish_mode = self.locked_project.publish_mode
        self.locked_project.publish_mode = Project.PUBLISH_MODE_PUBLISHED
        self.locked_project.save()

        project = self.locked_project
        user = self.regular_user
        circuits_group = Group.objects.get(name='123dcircuits')
        user.groups.add(circuits_group)

        self.assertFalse(project.can_edit(user))
        self.assertFalse(project.can_teach(user))
        self.assertTrue(project.can_view(user))
        self.assertTrue(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        self.assertFalse(project.can_publish(user))

        # Cleanup
        self.locked_project.publish_mode = old_publish_mode
        self.locked_project.save()
        user.groups.remove(circuits_group)

    def test_permissions_for_reviewer_on_project_in_review_mode(self):

        old_publish_mode = self.locked_project.publish_mode
        self.locked_project.publish_mode = Project.PUBLISH_MODE_REVIEW
        self.locked_project.save()

        project = self.locked_project
        user = self.regular_user
        user.is_superuser = True
        user.save()

        self.assertFalse(project.can_edit(user))
        self.assertFalse(project.can_teach(user))
        self.assertTrue(project.can_view(user))
        self.assertTrue(project.can_preview(user))
        self.assertTrue(project.can_reedit(user))
        self.assertTrue(project.can_publish(user))

        # Cleanup
        self.locked_project.publish_mode = old_publish_mode
        self.locked_project.save()
        user.is_superuser = False
        user.save()

    def test_permissions_for_reviewer_on_project_in_ready_mode(self):

        old_publish_mode = self.locked_project.publish_mode
        self.locked_project.publish_mode = Project.PUBLISH_MODE_READY
        self.locked_project.save()

        project = self.locked_project
        user = self.regular_user
        user.is_superuser = True
        user.save()

        self.assertFalse(project.can_edit(user))
        # self.assertFalse(project.can_teach(user))
        self.assertTrue(project.can_view(user))
        self.assertTrue(project.can_preview(user))
        self.assertTrue(project.can_reedit(user))
        self.assertTrue(project.can_publish(user))

        # Cleanup
        self.locked_project.publish_mode = old_publish_mode
        self.locked_project.save()
        user.is_superuser = False
        user.save()


    def test_permissions_for_regular_user_on_regular_project_in_edit_mode(self):

        old_publish_mode = self.regular_project.publish_mode
        self.regular_project.publish_mode = Project.PUBLISH_MODE_EDIT
        self.regular_project.save()

        project = self.regular_project
        user = self.regular_user

        self.assertFalse(project.can_edit(user))
        self.assertFalse(project.can_teach(user))
        self.assertFalse(project.can_view(user))
        self.assertFalse(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        self.assertFalse(project.can_publish(user))

        # Cleanup
        self.regular_project.publish_mode = old_publish_mode
        self.regular_project.save()

    def test_permissions_for_regular_user_on_regular_project_in_review_mode(self):

        old_publish_mode = self.regular_project.publish_mode
        self.regular_project.publish_mode = Project.PUBLISH_MODE_REVIEW
        self.regular_project.save()

        project = self.regular_project
        user = self.regular_user

        self.assertFalse(project.can_edit(user))
        self.assertFalse(project.can_teach(user))
        self.assertFalse(project.can_view(user))
        self.assertFalse(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        self.assertFalse(project.can_publish(user))

        # Cleanup
        self.regular_project.publish_mode = old_publish_mode
        self.regular_project.save()

    def test_permissions_for_regular_user_on_regular_project_in_ready_mode(self):

        old_publish_mode = self.regular_project.publish_mode
        self.regular_project.publish_mode = Project.PUBLISH_MODE_READY
        self.regular_project.save()

        project = self.regular_project
        user = self.regular_user

        self.assertFalse(project.can_edit(user))
        self.assertFalse(project.can_teach(user))
        self.assertFalse(project.can_view(user))
        self.assertFalse(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        self.assertFalse(project.can_publish(user))

        # Cleanup
        self.regular_project.publish_mode = old_publish_mode
        self.regular_project.save()

    def test_permissions_for_regular_user_on_regular_project_in_published_mode(self):

        old_publish_mode = self.regular_project.publish_mode
        self.regular_project.publish_mode = Project.PUBLISH_MODE_PUBLISHED
        self.regular_project.save()

        project = self.regular_project
        user = self.regular_user

        self.assertFalse(project.can_edit(user))
        self.assertTrue(project.can_teach(user))
        self.assertTrue(project.can_view(user))
        self.assertTrue(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        self.assertFalse(project.can_publish(user))

        # Cleanup
        self.regular_project.publish_mode = old_publish_mode
        self.regular_project.save()

    def test_permissions_for_regular_child_user_on_regular_project_in_edit_mode(self):

        old_publish_mode = self.regular_project.publish_mode
        self.regular_project.publish_mode = Project.PUBLISH_MODE_EDIT
        self.regular_project.save()

        project = self.regular_project
        user = self.regular_user
        user.is_child = True
        user.save()

        self.assertFalse(project.can_edit(user))
        self.assertFalse(project.can_teach(user))
        self.assertFalse(project.can_view(user))
        self.assertFalse(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        self.assertFalse(project.can_publish(user))

        # Cleanup
        self.regular_project.publish_mode = old_publish_mode
        self.regular_project.save()
        user.is_child = False
        user.save()

    def test_permissions_for_regular_child_user_on_regular_project_in_review_mode(self):

        old_publish_mode = self.regular_project.publish_mode
        self.regular_project.publish_mode = Project.PUBLISH_MODE_REVIEW
        self.regular_project.save()

        project = self.regular_project
        user = self.regular_user
        user.is_child = True
        user.save()

        self.assertFalse(project.can_edit(user))
        self.assertFalse(project.can_teach(user))
        self.assertFalse(project.can_view(user))
        self.assertFalse(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        self.assertFalse(project.can_publish(user))

        # Cleanup
        self.regular_project.publish_mode = old_publish_mode
        self.regular_project.save()
        user.is_child = False
        user.save()

    def test_permissions_for_regular_child_user_on_regular_project_in_ready_mode(self):

        old_publish_mode = self.regular_project.publish_mode
        self.regular_project.publish_mode = Project.PUBLISH_MODE_READY
        self.regular_project.save()

        project = self.regular_project
        user = self.regular_user
        user.is_child = True
        user.save()

        self.assertFalse(project.can_edit(user))
        self.assertFalse(project.can_teach(user))
        self.assertFalse(project.can_view(user))
        self.assertFalse(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        self.assertFalse(project.can_publish(user))

        # Cleanup
        self.regular_project.publish_mode = old_publish_mode
        self.regular_project.save()
        user.is_child = False
        user.save()

    def test_permissions_for_regular_child_user_on_regular_project_in_published_mode(self):

        old_publish_mode = self.regular_project.publish_mode
        self.regular_project.publish_mode = Project.PUBLISH_MODE_PUBLISHED
        self.regular_project.save()

        project = self.regular_project
        user = self.regular_user
        user.is_child = True
        user.save()

        self.assertFalse(project.can_edit(user))
        self.assertFalse(project.can_teach(user))
        self.assertTrue(project.can_view(user))
        self.assertTrue(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        self.assertFalse(project.can_publish(user))

        # Cleanup
        self.regular_project.publish_mode = old_publish_mode
        self.regular_project.save()
        user.is_child = False
        user.save()

    def test_permissions_for_application_user_on_regular_project_in_edit_mode(self):

        old_publish_mode = self.regular_project.publish_mode
        self.regular_project.publish_mode = Project.PUBLISH_MODE_EDIT
        self.regular_project.save()

        project = self.regular_project
        user = self.regular_user
        circuits_group = Group.objects.get(name='123dcircuits')
        user.groups.add(circuits_group)

        self.assertFalse(project.can_edit(user))
        self.assertFalse(project.can_teach(user))
        self.assertTrue(project.can_view(user))
        self.assertTrue(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        self.assertFalse(project.can_publish(user))

        # Cleanup
        self.regular_project.publish_mode = old_publish_mode
        self.regular_project.save()
        user.groups.remove(circuits_group)

    def test_permissions_for_application_user_on_regular_project_in_review_mode(self):

        old_publish_mode = self.regular_project.publish_mode
        self.regular_project.publish_mode = Project.PUBLISH_MODE_REVIEW
        self.regular_project.save()

        project = self.regular_project
        user = self.regular_user
        circuits_group = Group.objects.get(name='123dcircuits')
        user.groups.add(circuits_group)

        self.assertFalse(project.can_edit(user))
        self.assertFalse(project.can_teach(user))
        self.assertTrue(project.can_view(user))
        self.assertTrue(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        self.assertFalse(project.can_publish(user))

        # Cleanup
        self.regular_project.publish_mode = old_publish_mode
        self.regular_project.save()
        user.groups.remove(circuits_group)

    def test_permissions_for_application_user_on_regular_project_in_ready_mode(self):

        old_publish_mode = self.regular_project.publish_mode
        self.regular_project.publish_mode = Project.PUBLISH_MODE_READY
        self.regular_project.save()

        project = self.regular_project
        user = self.regular_user
        circuits_group = Group.objects.get(name='123dcircuits')
        user.groups.add(circuits_group)

        self.assertFalse(project.can_edit(user))
        self.assertFalse(project.can_teach(user))
        self.assertTrue(project.can_view(user))
        self.assertTrue(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        self.assertFalse(project.can_publish(user))

        # Cleanup
        self.regular_project.publish_mode = old_publish_mode
        self.regular_project.save()
        user.groups.remove(circuits_group)

    def test_permissions_for_application_user_on_regular_project_in_published_mode(self):

        old_publish_mode = self.regular_project.publish_mode
        self.regular_project.publish_mode = Project.PUBLISH_MODE_PUBLISHED
        self.regular_project.save()

        project = self.regular_project
        user = self.regular_user
        circuits_group = Group.objects.get(name='123dcircuits')
        user.groups.add(circuits_group)

        self.assertFalse(project.can_edit(user))
        self.assertTrue(project.can_teach(user))
        self.assertTrue(project.can_view(user))
        self.assertTrue(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        self.assertFalse(project.can_publish(user))

        # Cleanup
        self.regular_project.publish_mode = old_publish_mode
        self.regular_project.save()
        user.groups.remove(circuits_group)

    def test_permissions_for_anonymous_user_on_regular_project_in_edit_mode(self):

        old_publish_mode = self.regular_project.publish_mode
        self.regular_project.publish_mode = Project.PUBLISH_MODE_EDIT
        self.regular_project.save()

        project = self.regular_project
        user = AnonymousUser()

        self.assertFalse(project.can_edit(user))
        self.assertFalse(project.can_teach(user))
        self.assertFalse(project.can_view(user))
        self.assertFalse(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        self.assertFalse(project.can_publish(user))

        # Cleanup
        self.regular_project.publish_mode = old_publish_mode
        self.regular_project.save()

    def test_permissions_for_anonymous_user_on_regular_project_in_review_mode(self):

        old_publish_mode = self.regular_project.publish_mode
        self.regular_project.publish_mode = Project.PUBLISH_MODE_REVIEW
        self.regular_project.save()

        project = self.regular_project
        user = AnonymousUser()

        self.assertFalse(project.can_edit(user))
        self.assertFalse(project.can_teach(user))
        self.assertFalse(project.can_view(user))
        self.assertFalse(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        self.assertFalse(project.can_publish(user))

        # Cleanup
        self.regular_project.publish_mode = old_publish_mode
        self.regular_project.save()

    def test_permissions_for_anonymous_user_on_regular_project_in_ready_mode(self):

        old_publish_mode = self.regular_project.publish_mode
        self.regular_project.publish_mode = Project.PUBLISH_MODE_READY
        self.regular_project.save()

        project = self.regular_project
        user = AnonymousUser()

        self.assertFalse(project.can_edit(user))
        self.assertFalse(project.can_teach(user))
        self.assertFalse(project.can_view(user))
        self.assertFalse(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        self.assertFalse(project.can_publish(user))

        # Cleanup
        self.regular_project.publish_mode = old_publish_mode
        self.regular_project.save()

    def test_permissions_for_anonymous_user_on_regular_project_in_published_mode(self):

        old_publish_mode = self.regular_project.publish_mode
        self.regular_project.publish_mode = Project.PUBLISH_MODE_PUBLISHED
        self.regular_project.save()

        project = self.regular_project
        user = AnonymousUser()

        self.assertFalse(project.can_edit(user))
        self.assertFalse(project.can_teach(user))
        self.assertFalse(project.can_view(user))
        self.assertTrue(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        self.assertFalse(project.can_publish(user))

        # Cleanup
        self.regular_project.publish_mode = old_publish_mode
        self.regular_project.save()


    def test_permissions_for_regular_user_on_locked_project_in_edit_mode(self):

        old_publish_mode = self.locked_project.publish_mode
        self.locked_project.publish_mode = Project.PUBLISH_MODE_EDIT
        self.locked_project.save()

        project = self.locked_project
        user = self.regular_user

        self.assertFalse(project.can_edit(user))
        self.assertFalse(project.can_teach(user))
        self.assertFalse(project.can_view(user))
        self.assertFalse(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        self.assertFalse(project.can_publish(user))

        # Cleanup
        self.locked_project.publish_mode = old_publish_mode
        self.locked_project.save()

    def test_permissions_for_regular_user_on_locked_project_in_review_mode(self):

        old_publish_mode = self.locked_project.publish_mode
        self.locked_project.publish_mode = Project.PUBLISH_MODE_REVIEW
        self.locked_project.save()

        project = self.locked_project
        user = self.regular_user

        self.assertFalse(project.can_edit(user))
        self.assertFalse(project.can_teach(user))
        self.assertFalse(project.can_view(user))
        self.assertFalse(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        self.assertFalse(project.can_publish(user))

        # Cleanup
        self.locked_project.publish_mode = old_publish_mode
        self.locked_project.save()

    def test_permissions_for_regular_user_on_locked_project_in_ready_mode(self):

        old_publish_mode = self.locked_project.publish_mode
        self.locked_project.publish_mode = Project.PUBLISH_MODE_READY
        self.locked_project.save()

        project = self.locked_project
        user = self.regular_user

        self.assertFalse(project.can_edit(user))
        self.assertFalse(project.can_teach(user))
        self.assertFalse(project.can_view(user))
        self.assertFalse(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        self.assertFalse(project.can_publish(user))

        # Cleanup
        self.locked_project.publish_mode = old_publish_mode
        self.locked_project.save()

    def test_permissions_for_regular_user_on_locked_project_in_published_mode(self):

        old_publish_mode = self.locked_project.publish_mode
        self.locked_project.publish_mode = Project.PUBLISH_MODE_PUBLISHED
        self.locked_project.save()

        project = self.locked_project
        user = self.regular_user

        self.assertFalse(project.can_edit(user))
        self.assertFalse(project.can_teach(user))
        self.assertFalse(project.can_view(user))
        self.assertTrue(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        self.assertFalse(project.can_publish(user))

        # Cleanup
        self.locked_project.publish_mode = old_publish_mode
        self.locked_project.save()

    def test_permissions_for_anonymous_user_on_locked_project_in_edit_mode(self):

        old_publish_mode = self.locked_project.publish_mode
        self.locked_project.publish_mode = Project.PUBLISH_MODE_EDIT
        self.locked_project.save()

        project = self.locked_project
        user = AnonymousUser()

        self.assertFalse(project.can_edit(user))
        self.assertFalse(project.can_teach(user))
        self.assertFalse(project.can_view(user))
        self.assertFalse(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        self.assertFalse(project.can_publish(user))

        # Cleanup
        self.locked_project.publish_mode = old_publish_mode
        self.locked_project.save()

    def test_permissions_for_anonymous_user_on_locked_project_in_review_mode(self):

        old_publish_mode = self.locked_project.publish_mode
        self.locked_project.publish_mode = Project.PUBLISH_MODE_REVIEW
        self.locked_project.save()

        project = self.locked_project
        user = AnonymousUser()

        self.assertFalse(project.can_edit(user))
        self.assertFalse(project.can_teach(user))
        self.assertFalse(project.can_view(user))
        self.assertFalse(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        self.assertFalse(project.can_publish(user))

        # Cleanup
        self.locked_project.publish_mode = old_publish_mode
        self.locked_project.save()

    def test_permissions_for_anonymous_user_on_locked_project_in_ready_mode(self):

        old_publish_mode = self.locked_project.publish_mode
        self.locked_project.publish_mode = Project.PUBLISH_MODE_READY
        self.locked_project.save()

        project = self.locked_project
        user = AnonymousUser()

        self.assertFalse(project.can_edit(user))
        self.assertFalse(project.can_teach(user))
        self.assertFalse(project.can_view(user))
        self.assertFalse(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        self.assertFalse(project.can_publish(user))

        # Cleanup
        self.locked_project.publish_mode = old_publish_mode
        self.locked_project.save()

    def test_permissions_for_anonymous_user_on_locked_project_in_published_mode(self):

        old_publish_mode = self.locked_project.publish_mode
        self.locked_project.publish_mode = Project.PUBLISH_MODE_PUBLISHED
        self.locked_project.save()

        project = self.locked_project
        user = AnonymousUser()

        self.assertFalse(project.can_edit(user))
        self.assertFalse(project.can_teach(user))
        self.assertFalse(project.can_view(user))
        self.assertTrue(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        self.assertFalse(project.can_publish(user))

        # Cleanup
        self.locked_project.publish_mode = old_publish_mode
        self.locked_project.save()


    def test_permissions_for_purchase_view_user_on_locked_project_in_edit_mode(self):

        old_publish_mode = self.locked_project.publish_mode
        self.locked_project.publish_mode = Project.PUBLISH_MODE_EDIT
        self.locked_project.save()

        project = self.locked_project
        user = self.regular_user
        purchase = Purchase(user=user, project=self.locked_project, permission=Purchase.VIEW_PERM)
        purchase.save()

        self.assertFalse(project.can_edit(user))
        self.assertFalse(project.can_teach(user))
        self.assertFalse(project.can_view(user))
        self.assertFalse(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        self.assertFalse(project.can_publish(user))

        # Cleanup
        self.locked_project.publish_mode = old_publish_mode
        self.locked_project.save()

    def test_permissions_for_purchase_view_user_on_locked_project_in_review_mode(self):

        old_publish_mode = self.locked_project.publish_mode
        self.locked_project.publish_mode = Project.PUBLISH_MODE_REVIEW
        self.locked_project.save()

        project = self.locked_project
        user = self.regular_user
        purchase = Purchase(user=user, project=self.locked_project, permission=Purchase.VIEW_PERM)
        purchase.save()

        self.assertFalse(project.can_edit(user))
        self.assertFalse(project.can_teach(user))
        self.assertFalse(project.can_view(user))
        self.assertFalse(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        self.assertFalse(project.can_publish(user))

        # Cleanup
        self.locked_project.publish_mode = old_publish_mode
        self.locked_project.save()

    def test_permissions_for_purchase_view_user_on_locked_project_in_ready_mode(self):

        old_publish_mode = self.locked_project.publish_mode
        self.locked_project.publish_mode = Project.PUBLISH_MODE_READY
        self.locked_project.save()

        project = self.locked_project
        user = self.regular_user
        purchase = Purchase(user=user, project=self.locked_project, permission=Purchase.VIEW_PERM)
        purchase.save()

        self.assertFalse(project.can_edit(user))
        self.assertFalse(project.can_teach(user))
        self.assertFalse(project.can_view(user))
        self.assertFalse(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        self.assertFalse(project.can_publish(user))

        # Cleanup
        self.locked_project.publish_mode = old_publish_mode
        self.locked_project.save()

    def test_permissions_for_purchase_view_user_on_locked_project_in_published_mode(self):

        old_publish_mode = self.locked_project.publish_mode
        self.locked_project.publish_mode = Project.PUBLISH_MODE_PUBLISHED
        self.locked_project.save()

        project = self.locked_project
        user = self.regular_user
        purchase = Purchase(user=user, project=self.locked_project, permission=Purchase.VIEW_PERM)
        purchase.save()

        self.assertFalse(project.can_edit(user))
        self.assertFalse(project.can_teach(user))
        self.assertTrue(project.can_view(user))
        self.assertTrue(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        self.assertFalse(project.can_publish(user))

        # Cleanup
        self.locked_project.publish_mode = old_publish_mode
        self.locked_project.save()

    def test_permissions_for_purchase_teach_user_on_locked_project_in_edit_mode(self):

        old_publish_mode = self.locked_project.publish_mode
        self.locked_project.publish_mode = Project.PUBLISH_MODE_EDIT
        self.locked_project.save()

        project = self.locked_project
        user = self.regular_user
        purchase = Purchase(user=user, project=self.locked_project, permission=Purchase.TEACH_PERM)
        purchase.save()

        self.assertFalse(project.can_edit(user))
        self.assertFalse(project.can_teach(user))
        self.assertFalse(project.can_view(user))
        self.assertFalse(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        self.assertFalse(project.can_publish(user))

        # Cleanup
        self.locked_project.publish_mode = old_publish_mode
        self.locked_project.save()

    def test_permissions_for_purchase_teach_user_on_locked_project_in_review_mode(self):

        old_publish_mode = self.locked_project.publish_mode
        self.locked_project.publish_mode = Project.PUBLISH_MODE_REVIEW
        self.locked_project.save()

        project = self.locked_project
        user = self.regular_user
        purchase = Purchase(user=user, project=self.locked_project, permission=Purchase.TEACH_PERM)
        purchase.save()

        self.assertFalse(project.can_edit(user))
        self.assertFalse(project.can_teach(user))
        self.assertFalse(project.can_view(user))
        self.assertFalse(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        self.assertFalse(project.can_publish(user))

        # Cleanup
        self.locked_project.publish_mode = old_publish_mode
        self.locked_project.save()

    def test_permissions_for_purchase_teach_user_on_locked_project_in_ready_mode(self):

        old_publish_mode = self.locked_project.publish_mode
        self.locked_project.publish_mode = Project.PUBLISH_MODE_READY
        self.locked_project.save()

        project = self.locked_project
        user = self.regular_user
        purchase = Purchase(user=user, project=self.locked_project, permission=Purchase.TEACH_PERM)
        purchase.save()

        self.assertFalse(project.can_edit(user))
        self.assertFalse(project.can_teach(user))
        self.assertFalse(project.can_view(user))
        self.assertFalse(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        self.assertFalse(project.can_publish(user))

        # Cleanup
        self.locked_project.publish_mode = old_publish_mode
        self.locked_project.save()

    def test_permissions_for_purchase_teach_user_on_locked_project_in_published_mode(self):

        old_publish_mode = self.locked_project.publish_mode
        self.locked_project.publish_mode = Project.PUBLISH_MODE_PUBLISHED
        self.locked_project.save()

        project = self.locked_project
        user = self.regular_user
        purchase = Purchase(user=user, project=self.locked_project, permission=Purchase.TEACH_PERM)
        purchase.save()

        self.assertFalse(project.can_edit(user))
        self.assertTrue(project.can_teach(user))
        self.assertTrue(project.can_view(user))
        self.assertTrue(project.can_preview(user))
        self.assertFalse(project.can_reedit(user))
        self.assertFalse(project.can_publish(user))

        # Cleanup
        self.locked_project.publish_mode = old_publish_mode
        self.locked_project.save()



    def test_get_permission_for_user_purchased_no_prefetch(self):
        """Check that even if no one has prefetched the purchases of the project, the result is correct.

        This test is following a bug in get_permission_for_user.

        The bug was that get_permission_for_user relied on self.purchases . 

        That's usually okay, because the view prefetches the purchases and filters
        them by user. The problem happens when we get to get_permission_for_user 
        and no one filtered purchases. Then, purchases will just get a random purchase.

        If that random purchase is not of user "user", then we'll get incorrect results.
        """

        user = self.regular_user

        another_user = get_user_model().objects.exclude(
            id__in=[user.id, self.locked_project.owner.id],
        ).first()

        purchase = Purchase(
            user=another_user,
            project=self.locked_project,
            permission=Purchase.VIEW_PERM
        )
        purchase.save()

        self.assertEqual(
            self.locked_project.get_permission_for_user(another_user),
            Project.PERMS['TEACH'],
        )

        purchase.delete()

    def test_get_permission_for_user_delegate_no_prefetch(self):
        """Check that even if no one has prefetched the project owner delegates, the result is correct."""

        user = self.regular_user

        another_user = get_user_model().objects.exclude(
            id__in=[user.id, self.locked_project.owner.id],
        ).first()

        another_user_delegate = OwnerDelegate.objects.create(owner=self.locked_project.owner, user=another_user)

        self.assertEqual(
            self.locked_project.get_permission_for_user(another_user),
            Project.PERMS['TEACH'],
        )

        # Cleanup
        another_user_delegate.delete()


    # Test Project.can_edit
    # ####################################

    def test_get_permission_for_edit_when_no_editor_set_should_pass(self):
        project = Project.objects.all().first()
        user = self.regular_user

        self.assertFalse(project.is_user_edit_locked(user))

    def test_get_permission_for_edit_when_editor_set_should_fail(self):
        project = Project.objects.all().first()
        user = self.regular_user

        # set current editor
        current_editor = get_user_model().objects.exclude(id=user.id).first()
        project.current_editor_id = current_editor.id
        project.save()

        self.assertTrue(project.is_user_edit_locked(user))

    def test_get_permission_for_edit_for_superuser_when_editor_set_should_fail(self):
        project = Project.objects.all().first()
        user = self.regular_user
        user.is_superuser = True
        user.save()

        # set current editor
        current_editor = get_user_model().objects.exclude(id=user.id).first()
        project.current_editor_id = current_editor.id
        project.save()

        self.assertTrue(project.is_user_edit_locked(user))

        self.client.force_authenticate(user)
        resp = self.client.patch(
            reverse('api:project-detail', kwargs={'pk': project.pk}),
            json.dumps({}),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 403)

        user.is_superuser = False
        user.save()

    def test_get_permission_for_edit_when_editor_set_using_override_key_should_pass(self):
        project = Project.objects.all().first()
        user = self.regular_user

        # set current editor
        current_editor = get_user_model().objects.exclude(id=user.id).first()
        project.current_editor_id = current_editor.id
        project.save()

        self.assertFalse(project.is_user_edit_locked(user, force_edit_from_id=current_editor.id))

    def test_get_permission_for_edit_when_editor_set_using_zero_key_should_pass(self):
        project = Project.objects.all().first()
        user = self.regular_user

        # set current editor
        current_editor  =get_user_model().objects.exclude(id=user.id).first()
        project.current_editor_id = current_editor.id
        project.save()

        self.assertFalse(project.is_user_edit_locked(user, force_edit_from_id=0))

    def test_superuser_cannot_edit_lock_project_not_in_edit_mode(self):
        project = Project.objects.all().first()
        user = self.regular_user
        user.is_superuser = True
        user.save()
        self.client.force_authenticate(user)

        for publish_mode, _ in Project.PUBLISH_MODES:
            if publish_mode == Project.PUBLISH_MODE_EDIT:
                continue

            project.publish_mode = publish_mode
            project.save()

            resp = self.client.patch(
                reverse('api:project-detail', kwargs={'pk': project.pk}),
                json.dumps({
                    'currEditor': {'id': user.id},
                }),
                content_type='application/json',
            )
            self.assertEqual(resp.status_code, 400)
            self.assertIn('currEditor', resp.data)

        user.is_superuser = False
        user.save()


    # Test Serializing lessons
    # ########################

    def test_lessons_serializer_drops_app_blob_in_preview_mode(self):

        user = self.regular_user

        ls = LessonSerializer(
            self.locked_project.lessons.first(),
            context={
                'request': mock.Mock(user=user),
                'allowed': ['steps', 'stepsIds'],
            }
        )

        self.assertNotIn('applicationBlob', ls.data)
        self.assertNotIn('steps', ls.data)
        self.assertNotIn('stepsIds', ls.data)

    def test_lessons_serializer_has_app_blob_in_view_mode(self):

        user = self.regular_user

        purchase = Purchase(user=user, project=self.locked_project, permission=Purchase.VIEW_PERM)
        purchase.save()

        ls = LessonSerializer(
            self.locked_project.lessons.first(),
            context={
                'request': mock.Mock(user=user),
                'allowed': ['steps', 'stepsIds'],
            },
        )

        self.assertIn('applicationBlob', ls.data)
        self.assertIn('steps', ls.data)
        self.assertIn('stepsIds', ls.data)

        purchase.delete()

    def test_lessons_serializer_has_app_blob_in_teach_mode(self):

        user = self.regular_user

        purchase = Purchase(user=user, project=self.locked_project, permission=Purchase.TEACH_PERM)
        purchase.save()

        ls = LessonSerializer(
            self.locked_project.lessons.first(),
            context={
                'request': mock.Mock(user=user),
                'allowed': ['steps', 'stepsIds'],
            }
        )

        self.assertIn('applicationBlob', ls.data)
        self.assertIn('steps', ls.data)
        self.assertIn('stepsIds', ls.data)

        purchase.delete()

    def test_lessons_serializer_has_app_blob_in_edit_mode(self):

        ls = LessonSerializer(
            self.locked_project.lessons.first(),
            context={
                'request': mock.Mock(user=self.locked_project.owner),
                'allowed': ['steps', 'stepsIds'],
            }
        )

        self.assertIn('applicationBlob', ls.data)
        self.assertIn('steps', ls.data)
        self.assertIn('stepsIds', ls.data)


    # Test Serializing steps
    # ######################

    def test_step_list_unauthorized_in_preview_mode(self):

        user = self.regular_user

        self.client.force_authenticate(user)

        resp = self.client.get(reverse('api:project-lesson-step-list', kwargs={
            'project_pk': self.locked_project.id,
            'lesson_pk': self.step.lesson_id,
        }))

        self.assertEqual(resp.status_code, 403)

    def test_step_detail_unauthorized_in_preview_mode(self):

        user = self.regular_user

        self.client.force_authenticate(user)

        resp = self.client.get(reverse('api:project-lesson-step-detail', kwargs={
            'project_pk': self.locked_project.id,
            'lesson_pk': self.step.lesson_id,
            'order': self.step.order,
        }))

        self.assertEqual(resp.status_code, 403)

    def test_step_list_unauthorized_in_view_mode(self):

        user = self.regular_user

        purchase = Purchase(user=user, project=self.locked_project, permission=Purchase.VIEW_PERM)
        purchase.save()

        self.client.force_authenticate(user)

        resp = self.client.get(reverse('api:project-lesson-step-list', kwargs={
            'project_pk': self.locked_project.id,
            'lesson_pk': self.step.lesson_id,
        }))

        self.assertEqual(resp.status_code, 200)

        purchase.delete()

    def test_step_detail_unauthorized_in_teach_mode(self):

        user = self.regular_user

        purchase = Purchase(user=user, project=self.locked_project, permission=Purchase.TEACH_PERM)
        purchase.save()

        self.client.force_authenticate(user)

        resp = self.client.get(reverse('api:project-lesson-step-detail', kwargs={
            'project_pk': self.locked_project.id,
            'lesson_pk': self.step.lesson_id,
            'order': self.step.order,
        }))

        self.assertEqual(resp.status_code, 200)

        purchase.delete()

    # Add projects to classroom
    # #########################

    def test_cant_add_project_in_view_permission(self):

        user = self.regular_user

        purchase = Purchase(user=user, project=self.locked_project, permission=Purchase.VIEW_PERM)
        purchase.save()

        self.client.force_authenticate(user)

        classroom = Classroom(title='my class', owner=user, code='1234')
        classroom.save()
        
        resp = self.client.patch(
            reverse('api:classroom-detail', kwargs={'pk': classroom.id}) + '?embed=projectsIds', 
            json.dumps({
                'projectsIds': [self.locked_project.id],
            }, cls=DjangoJSONEncoder),
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 400)
        self.assertIn('projectsIds', resp.data)

        classroom.delete()
        purchase.delete()

    def test_cant_add_project_in_edit_permission(self):

        user = self.locked_project.owner
        self.client.force_authenticate(user)

        old_publish_mode = self.locked_project.publish_mode
        self.locked_project.publish_mode = Project.PUBLISH_MODE_EDIT
        self.locked_project.save()

        classroom = Classroom(title='my class', owner=user, code='1234')
        classroom.save()

        resp = self.client.patch(
            reverse('api:classroom-detail', kwargs={'pk': classroom.id}) + '?embed=projectsIds',
            json.dumps({
                'projectsIds': [self.locked_project.id],
            }, cls=DjangoJSONEncoder),
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 400)
        self.assertIn('projectsIds', resp.data)

        # Cleanup
        self.locked_project.publish_mode = old_publish_mode
        self.locked_project.save()
        classroom.delete()

    def test_can_add_project_with_teach_permission(self):
        
        user = self.regular_user

        purchase = Purchase(user=user, project=self.locked_project, permission=Purchase.TEACH_PERM)
        purchase.save()

        self.client.force_authenticate(user)

        classroom = Classroom(title='my class', owner=user, code='1234')
        classroom.save()

        resp = self.client.patch(
            reverse('api:classroom-detail', kwargs={'pk': classroom.id}) + '?embed=projectsIds', 
            json.dumps({
                'projectsIds': [self.locked_project.id],
            }, cls=DjangoJSONEncoder),
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 200)

        classroom.delete()
        purchase.delete()

    def test_cant_add_locked_project_in_view_permission(self):

        user = self.regular_user

        purchase = Purchase(user=user, project=self.locked_project, permission=Purchase.VIEW_PERM)
        purchase.save()

        classroom = Classroom(title='my class', owner=user, code='1234')
        classroom.save()

        self.client.force_authenticate(user)

        resp = self.client.patch(
            reverse('api:classroom-detail', kwargs={'pk': classroom.id}) + '?embed=projectsIds', 
            json.dumps({
                'projectsIds': [self.locked_project.id],
            }, cls=DjangoJSONEncoder),
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 400)
        self.assertIn('projectsIds', resp.data)

        purchase.delete()

    def test_cant_create_classroom_with_locked_project_in_view_permission(self):

        user = self.regular_user

        purchase = Purchase(user=user, project=self.locked_project, permission=Purchase.VIEW_PERM)
        purchase.save()

        self.client.force_authenticate(user)

        resp = self.client.post(
            reverse('api:classroom-list') + '?embed=projectsIds', 
            json.dumps({
                'title': 'My awesome class',
                'projectsIds': [self.locked_project.id],
            }, cls=DjangoJSONEncoder),
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 400)
        self.assertIn('projectsIds', resp.data)

        purchase.delete()

    def test_cant_create_classroom_with_locked_project_in_edit_permission(self):

        user = self.locked_project.owner
        self.client.force_authenticate(user)

        old_publish_mode = self.locked_project.publish_mode
        self.locked_project.publish_mode = Project.PUBLISH_MODE_EDIT
        self.locked_project.save()

        resp = self.client.post(
            reverse('api:classroom-list') + '?embed=projectsIds',
            json.dumps({
                'title': 'My awesome class',
                'projectsIds': [self.locked_project.id],
            }, cls=DjangoJSONEncoder),
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 400)
        self.assertIn('projectsIds', resp.data)

        # Cleanup
        self.locked_project.publish_mode = old_publish_mode
        self.locked_project.save()

    def test_cant_add_project_with_preview_permission(self):
        
        user = self.regular_user

        self.client.force_authenticate(user)

        classroom = Classroom(title='my class', owner=user, code='1234')
        classroom.save()
        
        cs = ClassroomSerializer(
            classroom,
            data={
                'projectsIds': [self.locked_project.id],
            },
            context={
                'request': mock.Mock(user=user),
                'allowed': ['projectsIds'],
            }
        )

        self.assertFalse(cs.is_valid())
        self.assertIn('projectsIds', cs.errors)
        self.assertIn('permission', cs.errors['projectsIds'][0])

        classroom.delete()

    def test_superuser_can_add_project_not_purchased(self):
        
        superuser = get_user_model().objects.exclude(
            id=self.locked_project.owner_id
        ).exclude(
            id__in=Purchase.objects.all().values_list('user_id', flat=True)
        ).filter(
            is_superuser=True,
        ).first()

        self.client.force_authenticate(superuser)

        classroom = Classroom(title='my class', owner=superuser, code='1234')
        classroom.save()
        
        cs = ClassroomSerializer(
            classroom,
            data={
                'projectsIds': [self.locked_project.id],
            },
            partial=True,
            context={
                'request': mock.Mock(user=superuser),
                'allowed': ['projectsIds'],
            }
        )

        self.assertTrue(cs.is_valid())

        classroom.delete()

    # Add Project to Classroom via PUT /classrooms/:id/projects/:id/
    # ##############################################################

    def test_cant_put_project_using_view_permissions(self):
        
        user = self.regular_user

        classroom = Classroom(title='my class', owner=user, code='1234')
        classroom.save()

        purchase = Purchase(user=user, project=self.locked_project, permission=Purchase.VIEW_PERM)
        purchase.save()

        self.client.force_authenticate(user)

        resp = self.client.put(
            reverse('api:classroom-project-detail', kwargs={
                'classroom_pk': classroom.id,
                'pk': self.locked_project.id,
            })
        )

        self.assertEqual(resp.status_code, 403)

        purchase.delete()
        classroom.delete()

    def test_cant_put_project_using_preview_permissions(self):
        
        user = self.regular_user

        classroom = Classroom(title='my class', owner=user, code='1234')
        classroom.save()

        self.client.force_authenticate(user)

        resp = self.client.put(
            reverse('api:classroom-project-detail', kwargs={
                'classroom_pk': classroom.id,
                'pk': self.locked_project.id,
            })
        )

        self.assertEqual(resp.status_code, 403)

        classroom.delete()

    def test_can_put_project_using_teach_permissions(self):

        user = self.regular_user

        classroom = Classroom(title='my class', owner=user, code='1234')
        classroom.save()

        purchase = Purchase(user=user, project=self.locked_project, permission=Purchase.TEACH_PERM)
        purchase.save()

        self.client.force_authenticate(user)

        resp = self.client.put(
            reverse('api:classroom-project-detail', kwargs={
                'classroom_pk': classroom.id,
                'pk': self.locked_project.id,
            }),
            json.dumps({
                'order': 0,
            }, cls=DjangoJSONEncoder),
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 200)

        purchase.delete()
        classroom.delete()

