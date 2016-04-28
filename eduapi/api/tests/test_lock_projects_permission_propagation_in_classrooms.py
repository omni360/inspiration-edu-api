import json
import mock

from datetime import datetime

from django.db import IntegrityError
from django.utils.timezone import now as utc_now
from django.contrib.auth import get_user_model
from django.core.urlresolvers import reverse
from django.core.serializers.json import DjangoJSONEncoder

from rest_framework.test import APITestCase as DRFTestCase

from .base_test_case import BaseTestCase

from marketplace.models import Purchase
from api.models import Project, Classroom, ProjectInClassroom, ClassroomState, ChildGuardian

from api.tasks import add_permissions_to_classroom_students


class ProjectPermissionsTests(BaseTestCase, DRFTestCase):
    
    fixtures = ['test_lock_projects_permission_propagation_in_classroom_fixture.json']

    def setUp(self):

        self.owner = get_user_model().objects.get(id=8)
        self.locked_projects = Project.objects.exclude(lock=Project.NO_LOCK)
        self.unlocked_projects = Project.objects.filter(lock=Project.NO_LOCK)

    def test_update_permissions_after_project_added(self):
        
        classroom = Classroom(title='my classroom', owner=self.owner)
        classroom.save()

        pic1 = ProjectInClassroom(project=self.unlocked_projects.first(), classroom=classroom, order=0)
        pic1.save()
        
        students = get_user_model().objects.exclude(id=self.owner.id)
        classroom_states = [ClassroomState(classroom=classroom, user=s, status=ClassroomState.APPROVED_STATUS) for s in students]
        [cs.save() for cs in classroom_states]

        curr_purchase_max_id = max(Purchase.objects.all().values_list('id', flat=True))

        # Adding project and calling the permissions task.
        pic2 = ProjectInClassroom(project=self.locked_projects.first(), classroom=classroom, order=1)
        pic2.save()
        add_permissions_to_classroom_students(classroom)


        for s in students:
            self.assertTrue(Purchase.objects.filter(
                user=s,
                project=self.locked_projects.first(),
                permission=Purchase.VIEW_PERM).exists()
            )

        # Cleanup
        [cs.delete() for cs in classroom_states]
        pic1.delete()
        pic2.delete()
        classroom.delete()
        Purchase.objects.filter(id__gte=curr_purchase_max_id).delete()


    def test_update_permissions_after_student_added(self):
        
        classroom = Classroom(title='my classroom', owner=self.owner)
        classroom.save()

        pic1 = ProjectInClassroom(project=self.unlocked_projects.first(), classroom=classroom, order=0)
        pic2 = ProjectInClassroom(project=self.locked_projects.first(), classroom=classroom, order=1)
        pic1.save()
        pic2.save()
        
        # Add all potential students, but 1.
        new_student = get_user_model().objects.exclude(
            id=self.owner.id,
            is_child=True,
        ).first()
        existing_students = get_user_model().objects.exclude(
            id__in=[self.owner.id, new_student.id]
        ).exclude(
            is_child=True
        )
        students = [new_student] + list(existing_students)
        classroom_states = [ClassroomState(
            classroom=classroom,
            user=s,
            status=ClassroomState.APPROVED_STATUS
        ) for s in students]
        [cs.save() for cs in classroom_states[1:]]

        purchases = [
            Purchase(user=s, project=self.locked_projects.first(), permission=Purchase.VIEW_PERM)
            for s in students[1:]
        ]
        [p.save() for p in purchases]

        timestamp = datetime.now()

        # Add last student and
        classroom_states[0].save()
        count_purchases = Purchase.objects.all().count()
        add_permissions_to_classroom_students(classroom)

        for s in students:
            self.assertEqual(Purchase.objects.filter(
                user=s,
                project=self.locked_projects.first(),
                permission=Purchase.VIEW_PERM).count(), 1
            )

        self.assertEqual(count_purchases + 1, Purchase.objects.all().count())

        # Cleanup
        [cs.delete() for cs in classroom_states]
        pic1.delete()
        pic2.delete()
        classroom.delete()
        [p.delete() for p in purchases]
        Purchase.objects.filter(added__gte=timestamp).delete()

    def test_update_permissions_propagates_to_moderators(self):
        
        classroom = Classroom(title='my classroom', owner=self.owner)
        classroom.save()

        pic = ProjectInClassroom(project=self.locked_projects.first(), classroom=classroom, order=0)
        pic.save()
        
        # Add all potential students, but 1.
        new_student = ChildGuardian.objects.exclude(
            guardian=self.owner
        ).first().child
        cs = ClassroomState(
            classroom=classroom,
            user=new_student,
            status=ClassroomState.APPROVED_STATUS
        )

        timestamp = utc_now()

        # Add last student and
        cs.save()
        add_permissions_to_classroom_students(classroom)

        self.assertTrue(Purchase.objects.filter(
            user=new_student,
            project=self.locked_projects.first(),
            permission=Purchase.VIEW_PERM).exists()
        )

        for cg in new_student.childguardian_guardian_set.all():
            p = Purchase.objects.filter(
                user=cg.guardian,
                project=self.locked_projects.first(),
                permission=Purchase.VIEW_PERM
            )
            self.assertTrue(p.exists())
            for purchase in p:
                self.assertGreaterEqual(purchase.added, timestamp)

        # Cleanup
        cs.delete()
        pic.delete()
        classroom.delete()
        Purchase.objects.filter(added__gte=timestamp).delete()

    def test_rejected_student_doesnt_get_access_to_project(self):
        """Make sure that if a student is rejected from the classroom, she doesn't get access to the locked project"""

        timestamp = utc_now()
        
        classroom = Classroom(title='my classroom', owner=self.owner)
        classroom.save()

        pic = ProjectInClassroom(project=self.locked_projects.first(), classroom=classroom, order=0)
        pic.save()
        
        # Add student.
        new_student = get_user_model().objects.filter(
            is_child=False
        ).exclude(
            id__in=Purchase.objects.all().values_list('user_id', flat=True)
        ).first()
        ClassroomState(
            classroom=classroom,
            user=new_student,
            status=ClassroomState.REJECTED_STATUS,
        ).save()

        purchases_count = Purchase.objects.all().count()

        add_permissions_to_classroom_students(classroom)

        self.assertEqual(purchases_count, Purchase.objects.all().count())

        # Cleanup
        ClassroomState.objects.filter(classroom=classroom).delete()
        ProjectInClassroom.objects.filter(classroom=classroom).delete()
        classroom.delete()
        Purchase.objects.filter(added__gte=timestamp).delete()

    def test_pending_student_doesnt_get_access_to_project(self):
        """Make sure that if a student is pending to the classroom, she doesn't get access to the locked project"""
        
        timestamp = utc_now()
        
        classroom = Classroom(title='my classroom', owner=self.owner)
        classroom.save()

        pic = ProjectInClassroom(project=self.locked_projects.first(), classroom=classroom, order=0)
        pic.save()
        
        # Add student.
        new_student = get_user_model().objects.filter(
            is_child=False
        ).exclude(
            id__in=Purchase.objects.all().values_list('user_id', flat=True)
        ).first()
        ClassroomState(
            classroom=classroom,
            user=new_student,
            status=ClassroomState.PENDING_STATUS,
        ).save()

        purchases_count = Purchase.objects.all().count()

        add_permissions_to_classroom_students(classroom)

        self.assertEqual(purchases_count, Purchase.objects.all().count())

        # Cleanup
        ClassroomState.objects.filter(classroom=classroom).delete()
        ProjectInClassroom.objects.filter(classroom=classroom).delete()
        classroom.delete()
        Purchase.objects.filter(added__gte=timestamp).delete()

    def test_update_permissions_propagation_multiple_moderators_for_same_child(self):
        
        classroom = Classroom(title='my classroom', owner=self.owner)
        classroom.save()

        pic = ProjectInClassroom(project=self.locked_projects.first(), classroom=classroom, order=0)
        pic.save()
        
        # Find a student with 2 moderators who are not the project owner.
        potential_students = get_user_model().objects.filter(
            id__in=ChildGuardian.objects.exclude(
                       guardian=self.owner
                    ).values_list('child_id', flat=True)
            )
        for s in potential_students:
            if s.childguardian_guardian_set.exclude(guardian=self.owner).count() > 1:
                new_student = s
                break

        cs = ClassroomState(
            classroom=classroom,
            user=new_student,
            status=ClassroomState.APPROVED_STATUS
        )

        timestamp = utc_now()

        # Add student to classroom
        cs.save()
        add_permissions_to_classroom_students(classroom)

        self.assertTrue(Purchase.objects.filter(
            user=new_student,
            project=self.locked_projects.first(),
            permission=Purchase.VIEW_PERM).exists()
        )

        # Check that all of the student's moderators got a permission to the project.
        for cg in new_student.childguardian_guardian_set.all():
            p = Purchase.objects.filter(
                user=cg.guardian,
                project=self.locked_projects.first(),
                permission=Purchase.VIEW_PERM
            )
            self.assertTrue(p.exists())
            for purchase in p:
                self.assertGreaterEqual(purchase.added, timestamp)

        # Cleanup
        cs.delete()
        pic.delete()
        classroom.delete()
        Purchase.objects.filter(added__gte=timestamp).delete()

    def test_update_permissions_same_moderator_for_different_children(self):
        classroom = Classroom(title='my classroom', owner=self.owner)
        classroom.save()

        pic = ProjectInClassroom(project=self.locked_projects.first(), classroom=classroom, order=0)
        pic.save()
        
        # Find a student with 2 moderators who are not the project owner.
        potential_moderators = get_user_model().objects.filter(
            id__in=ChildGuardian.objects.exclude(
                guardian=self.owner
            ).values_list('guardian_id', flat=True)
        ).exclude(id=self.owner.id)
        for m in potential_moderators:
            if m.childguardian_child_set.all().count() > 1:
                new_students = get_user_model().objects.filter(
                    id__in=m.childguardian_child_set.all().values_list('child_id', flat=True)
                )
                moderator = m
                break

        classroom_states = [ClassroomState(
            classroom=classroom,
            user=s,
            status=ClassroomState.APPROVED_STATUS
        ) for s in new_students]

        timestamp = utc_now()

        purchases_count = Purchase.objects.all().count()

        # Add student to classroom
        [cs.save() for cs in classroom_states]
        add_permissions_to_classroom_students(classroom)

        # Check that the moderator for the students got a view permission.
        p = Purchase.objects.filter(
            user=moderator,
            project=self.locked_projects.first(),
            permission=Purchase.VIEW_PERM
        )
        self.assertTrue(p.exists())

        # The expected amount of new purchases is the same as the amount of 
        # new students + their moderators.
        new_purchases = new_students.count() + get_user_model().objects.filter(
            childguardian_child_set__child_id__in=new_students.values_list('id', flat=True)
        ).distinct().count()
        self.assertEqual(purchases_count + new_purchases, Purchase.objects.all().count())

        # Cleanup
        [cs.delete() for cs in classroom_states]
        pic.delete()
        classroom.delete()
        Purchase.objects.filter(added__gte=timestamp).delete()

    def test_update_permissions_user_already_has_view_permission(self):
        
        timestamp = utc_now()

        classroom = Classroom(title='my classroom', owner=self.owner)
        classroom.save()

        pic = ProjectInClassroom(project=self.locked_projects.first(), classroom=classroom, order=0)
        pic.save()
        
        # Find an adult student.
        student = get_user_model().objects.filter(
            is_child=False,
        ).exclude(
            id=self.owner.id
        ).first()

        # The student already has a view permission
        purchase = Purchase(user=student, project=self.locked_projects.first(), permission=Purchase.VIEW_PERM)
        purchase.save()

        cs = ClassroomState(
            classroom=classroom,
            user=student,
            status=ClassroomState.APPROVED_STATUS
        )

        purchases_count = Purchase.objects.all().count()

        # Add student to classroom
        cs.save()
        add_permissions_to_classroom_students(classroom)

        # Check that the student still has a view permission.
        p = Purchase.objects.filter(
            user=student,
            project=self.locked_projects.first(),
            permission=Purchase.VIEW_PERM
        )
        self.assertTrue(p.exists())

        # The amount of purchases didn't change.
        self.assertEqual(purchases_count, Purchase.objects.all().count())

        # Cleanup
        cs.delete()
        pic.delete()
        classroom.delete()
        Purchase.objects.filter(added__gte=timestamp).delete()

    def test_update_permissions_user_already_has_teach_permission(self):
        
        timestamp = utc_now()

        classroom = Classroom(title='my classroom', owner=self.owner)
        classroom.save()

        pic = ProjectInClassroom(project=self.locked_projects.first(), classroom=classroom, order=0)
        pic.save()
        
        # Find an adult student.
        student = get_user_model().objects.filter(
            is_child=False,
        ).exclude(
            id=self.owner.id
        ).first()

        # The student already has a view permission
        purchase = Purchase(user=student, project=self.locked_projects.first(), permission=Purchase.TEACH_PERM)
        purchase.save()

        cs = ClassroomState(
            classroom=classroom,
            user=student,
            status=ClassroomState.APPROVED_STATUS
        )

        purchases_count = Purchase.objects.all().count()

        # Add student to classroom
        cs.save()
        add_permissions_to_classroom_students(classroom)

        # Check that the student still has a view permission.
        self.assertTrue(Purchase.objects.filter(
            user=student,
            project=self.locked_projects.first(),
            permission=Purchase.TEACH_PERM
        ).exists())

        # Student doesn't have an additional purchase with a view permission.
        self.assertFalse(Purchase.objects.filter(
            user=student,
            project=self.locked_projects.first(),
            permission=Purchase.VIEW_PERM
        ).exists())

        # The amount of purchases didn't change.
        self.assertEqual(purchases_count, Purchase.objects.all().count())

        # Cleanup
        cs.delete()
        pic.delete()
        classroom.delete()
        Purchase.objects.filter(added__gte=timestamp).delete()

    def test_update_permissions_called_when_project_added_to_classroom(self):
        
        timestamp = utc_now()
        
        classroom = Classroom(title='my classroom', owner=self.owner)
        classroom.save()
        
        # Add all adult students with no purchases.
        students = get_user_model().objects.filter(
            is_child=False
        ).exclude(
            id__in=Purchase.objects.all().values_list('user_id', flat=True)
        ).distinct()

        classroom_states = [ClassroomState(
            classroom=classroom,
            user=s,
            status=ClassroomState.APPROVED_STATUS
        ) for s in students]
        [cs.save() for cs in classroom_states]

        self.client.force_authenticate(self.owner)

        with mock.patch('api.tasks.add_permissions_to_classroom_students.delay') as my_mock:
            resp = self.client.put(
                reverse('api:classroom-project-detail', kwargs={
                    'classroom_pk': classroom.id,
                    'pk': self.locked_projects.first().id,
                }),
                json.dumps({'order': 0}, cls=DjangoJSONEncoder),
                content_type='application/json',
            )

            self.assertEqual(resp.status_code, 200)

            my_mock.assert_called_with(classroom)

        # Cleanup
        ClassroomState.objects.filter(classroom=classroom).delete()
        ProjectInClassroom.objects.filter(classroom=classroom).delete()
        classroom.delete()
        Purchase.objects.filter(added__gte=timestamp).delete()

    def test_update_permissions_called_when_student_added_to_classroom(self):
        
        timestamp = utc_now()
        
        classroom = Classroom(title='my classroom', owner=self.owner)
        classroom2 = Classroom(title='my classroom 2', owner=self.owner)
        classroom.save()
        classroom2.save()
        
        self.client.force_authenticate(self.owner)

        pic = ProjectInClassroom(project=self.locked_projects.first(), classroom=classroom, order=0)
        pic.save()

        new_student = get_user_model().objects.filter(
            is_child=False
        ).exclude(
            id__in=Purchase.objects.all().values_list('user_id', flat=True)
        ).first()

        ClassroomState(
            classroom=classroom2,
            user=new_student,
            status=ClassroomState.APPROVED_STATUS
        ).save()

        with mock.patch('api.tasks.add_permissions_to_classroom_students.delay') as my_mock:
            resp = self.client.put(reverse(
                'api:classroom-students-detail',  kwargs={
                    'classroom_pk': classroom.id,
                    'pk': new_student.id,
                }
            ))

            self.assertEqual(resp.status_code, 200)

            my_mock.assert_called_with(classroom)

        # Cleanup
        ClassroomState.objects.filter(classroom=classroom).delete()
        ProjectInClassroom.objects.filter(classroom=classroom).delete()
        classroom.delete()
        ClassroomState.objects.filter(classroom=classroom2).delete()
        classroom2.delete()
        Purchase.objects.filter(added__gte=timestamp).delete()

    def test_integrity_error_doesnt_cause_problems(self):

        timestamp = utc_now()
        
        classroom = Classroom(title='my classroom', owner=self.owner)
        classroom.save()

        pic = ProjectInClassroom(project=self.locked_projects.first(), classroom=classroom, order=0)
        pic.save()
        
        # Add all adult students with no purchases.
        students = get_user_model().objects.filter(
            is_child=False
        ).exclude(
            id__in=Purchase.objects.all().values_list('user_id', flat=True)
        ).distinct()
        classroom_states = [ClassroomState(
            classroom=classroom,
            user=s,
            status=ClassroomState.APPROVED_STATUS
        ) for s in students]

        # Add last student and
        [cs.save() for cs in classroom_states]

        # Patch Purchase.save() to raise an IntegrityError once.
        patcher = mock.patch('api.models.Purchase.save')
        my_mock = patcher.start()
        def side_effect(*args, **kwargs):
            patcher.stop()
            raise IntegrityError('boom')
        my_mock.side_effect = side_effect

        purchases_count = Purchase.objects.all().count()
        add_permissions_to_classroom_students(classroom)

        # Make sure that all of the purchases were added, but one.
        new_purchases = students.count() - 1
        self.assertEqual(purchases_count + new_purchases, Purchase.objects.all().count())

        # Cleanup
        [cs.delete() for cs in classroom_states]
        pic.delete()
        classroom.delete()
        Purchase.objects.filter(added__gte=timestamp).delete()
