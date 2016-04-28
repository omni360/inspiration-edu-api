import json
import unittest

from django.core.urlresolvers import reverse
from django.contrib.auth import get_user_model
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q
from django.test.utils import override_settings

from rest_framework.test import APITestCase as DRFTestCase

from edu_api_test_case import EduApiTestCase

from ..serializers import UserSerializer
from ..models import (
    Classroom,
    ClassroomState,
)

@override_settings(
    CELERY_ALWAYS_EAGER=True,
    BROKER_BACKEND='memory',
    DISABLE_SENDING_CELERY_EMAILS=True)
class StudentsTests(EduApiTestCase, DRFTestCase):
    '''
    Tests the Classroom API.
    '''

    fixtures = ['test_projects_fixture_1.json']
    classroom_pk = 1
    model = get_user_model()

    def get_all_user_objects(self):
        return Classroom.objects.get(id=self.classroom_pk).students.all()

    def api_test_init(self):
        super(StudentsTests, self).api_test_init()

        self.classroom_pk = 1
        self.classroom = Classroom.objects.get(pk=self.classroom_pk)
        self.put_actions = [
            # Successful PUT
            {
                'user': self.classroom.owner,
                'get_object': lambda: self.classroom.students.first(),
                'expected_result': 200,
            },
            # Not a student and not an owner.
            {
                'user': get_user_model().objects.exclude(id__in=
                    self.classroom.students.values_list('id', flat=True)
                ).exclude(id=self.classroom.owner_id).first(),
                'get_object': lambda: self.classroom.students.first(),
                'expected_result': 403,
            }, 
            # Is a student but not an owner.
            {
                'user': self.classroom.students.first(),
                'get_object': lambda: self.classroom.students.last(),
                'expected_result': 403,
            }, 
            # Not logged in.
            {
                'user': None,
                'get_object': lambda: self.classroom.students.first(),
                'expected_result': 401,
            }
        ]
        self.global_user = get_user_model().objects.filter(id=2)
        self.api_list_url = reverse('api:classroom-students-list', kwargs={'classroom_pk': self.classroom_pk})
        self.non_existant_obj_details_url = reverse('api:classroom-students-detail', kwargs={'classroom_pk': self.classroom_pk, 'pk': 4444})
        self.bulk_actions = ['post', 'put', 'delete']

        # There are no public objects.
        self.all_public_objects = get_user_model().objects.none()
        self.serializer = UserSerializer
        self.sort_key = 'id'
        self.pagination = True

    def get_api_details_url(self, obj):
        return reverse('api:classroom-students-detail', kwargs={'classroom_pk': self.classroom_pk, 'pk': obj.pk})

    def check_get_list_by_user(self, user, classroom):

        students = classroom.students.all()
        students_ids = [s.id for s in students]

        self.client.force_authenticate(user)

        resp = self.client.get(reverse('api:classroom-students-list', kwargs={'classroom_pk': classroom.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], len(students))

        for api_student in resp.data['results']:
            self.assertIn(api_student['id'], students_ids)

    def check_get_all_students_details_by_user(self, user, classroom):

        students = classroom.students.all()

        self.client.force_authenticate(user)

        for student in students:
    
            resp = self.client.get(reverse(
                'api:classroom-students-detail', 
                kwargs={'classroom_pk': classroom.pk, 'pk': student.pk}
            ))
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.data['id'], student.id)


    def test_get_list_everyone_can(self):
        '''User can't get list of students if not logged in'''

        self.client.force_authenticate(None)
        resp = self.client.get(self.api_list_url + '?pageSize=' + str(self.all_user_objects.count()))
        self.assertEqual(resp.status_code, 401)

    def test_get_choices_on_options_without_login(self):
        '''User can't make SAFE actions against students API if not logged in'''

        self.client.force_authenticate(None)
        resp = self.client.options(self.api_list_url)
        self.assertEqual(resp.status_code, 401)

    def test_students_list_viewable_by_students(self):
        '''Student in classroom can GET a list of students'''

        for classroom in Classroom.objects.all():
            for student in classroom.students.all():
                self.check_get_list_by_user(student, classroom)

    def test_students_list_viewable_by_classroom_owner(self):
        '''Classroom owner can GET a list of students'''
        
        for classroom in Classroom.objects.all():
            self.check_get_list_by_user(classroom.owner, classroom)


    def test_students_details_viewable_by_students(self):
        '''Student in classroom can GET a student's details'''

        for classroom in Classroom.objects.all():
            for student in classroom.students.all():
                self.check_get_all_students_details_by_user(student, classroom)

    def test_students_details_viewable_by_classroom_owner(self):
        '''Classroom owner can GET students details'''

        for classroom in Classroom.objects.all():
            self.check_get_all_students_details_by_user(classroom.owner, classroom)

    def test_cant_path_student(self):
        '''PATCH method is not allowed for students-details'''

        resp = self.client.patch(
            self.get_api_details_url(self.all_user_objects.first()),
            json.dumps({}, cls=DjangoJSONEncoder), 
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 405)

    def test_classroom_owner_can_add_student_from_her_students(self):
        '''Classroom owner can PUT a new user to a classroom that is her student in another classroom'''

        for classroom in Classroom.objects.all():
            self.client.force_authenticate(classroom.owner)

            user = get_user_model().objects.filter(
                #student in another classroom of the teacher:
                id__in=ClassroomState.objects.filter(
                        classroom__in=classroom.owner.authored_classrooms.all()
                    ).values('user'),
            ).exclude(
                #owner and children and students in current classroom:
                Q(id=classroom.owner.id) |
                Q(id__in=classroom.owner.children.all()) |
                Q(id__in=classroom.students.all())
            ).first()

            if not user:
                continue

            # ClassroomState doesn't exist.
            self.assertEqual(ClassroomState.objects.filter(
                classroom=classroom,
                user=user
            ).count(), 0)

            resp = self.client.put(
                reverse('api:classroom-students-detail', kwargs={
                    'classroom_pk': classroom.id,
                    'pk': user.pk
                }),
                json.dumps({}, cls=DjangoJSONEncoder), 
                content_type='application/json',
            )

            self.assertIn(resp.status_code, xrange(200,204))
            self.assertEqual(resp.data['id'], user.pk)

            # Delete the classroom.
            classroom_state = ClassroomState.objects.get(
                classroom=classroom,
                user=user
            )
            classroom_state.delete()

    def test_classroom_owner_can_add_student_from_her_children(self):
        '''Classroom owner can PUT a new user to a classroom that is her child'''

        for classroom in Classroom.objects.all():
            self.client.force_authenticate(classroom.owner)

            user = classroom.owner.children.exclude(
                #students:
                id__in=ClassroomState.objects.filter(
                        classroom__in=classroom.owner.authored_classrooms.all()
                    ).values('user')
            ).first()

            if not user:
                continue

            # ClassroomState doesn't exist.
            self.assertEqual(ClassroomState.objects.filter(
                classroom=classroom,
                user=user
            ).count(), 0)

            resp = self.client.put(
                reverse('api:classroom-students-detail', kwargs={
                    'classroom_pk': classroom.id,
                    'pk': user.pk
                }),
                json.dumps({}, cls=DjangoJSONEncoder),
                content_type='application/json',
            )

            self.assertIn(resp.status_code, xrange(200,204))
            self.assertEqual(resp.data['id'], user.pk)

            # Delete the classroom.
            classroom_state = ClassroomState.objects.get(
                classroom=classroom,
                user=user
            )
            classroom_state.delete()

    def test_classroom_owner_cannot_add_user_that_is_not_student_or_child(self):
        '''Classroom owner can not PUT a new user to a classroom that is not her student or child'''

        for classroom in Classroom.objects.all():
            self.client.force_authenticate(classroom.owner)

            user = get_user_model().objects.exclude(
                #students or children:
                Q(id__in=ClassroomState.objects.filter(
                        classroom__in=classroom.owner.authored_classrooms.all()
                    ).values('user')) |
                Q(id__in=classroom.owner.children.all())
            ).first()

            if not user:
                continue

            # ClassroomState doesn't exist.
            self.assertEqual(ClassroomState.objects.filter(
                classroom=classroom,
                user=user
            ).count(), 0)

            resp = self.client.put(
                reverse('api:classroom-students-detail', kwargs={
                    'classroom_pk': classroom.id,
                    'pk': user.pk
                }),
                json.dumps({}, cls=DjangoJSONEncoder),
                content_type='application/json',
            )
            self.assertEqual(resp.status_code, 400)
            self.assertIn('id', resp.data)

    def test_adding_existing_student_doesnt_do_anything(self):
        '''PUTing a student that's already in the classroom doesn't ruin the integrity of the database'''

        for classroom in Classroom.objects.all():
            self.client.force_authenticate(classroom.owner)

            for student in classroom.students.all():

                # There's one classroom state for the classroom and user.
                self.assertEqual(ClassroomState.objects.filter(
                    classroom=classroom,
                    user=student,
                ).count(), 1)

                resp = self.client.put(
                    reverse('api:classroom-students-detail', kwargs={
                        'classroom_pk': classroom.id,
                        'pk': student.pk
                    }),
                    json.dumps({}, cls=DjangoJSONEncoder), 
                    content_type='application/json',
                )

                # Request returned success.
                self.assertIn(resp.status_code, xrange(200, 204))

                # There's still one classroom state for the classroom and user.
                self.assertEqual(ClassroomState.objects.filter(
                    classroom=classroom,
                    user=student,
                ).count(), 1)

    def test_classroom_owner_can_change_student_status(self):
        '''Teacher can change the student status in his classroom'''

        for classroom in Classroom.objects.all():
            self.client.force_authenticate(classroom.owner)

            for registration in classroom.registrations.all():
                student = registration.user

                # There's one classroom state for the classroom and user.
                self.assertEqual(ClassroomState.objects.filter(
                    classroom=classroom,
                    user=student,
                ).count(), 1)

                student_status = registration.status
                new_student_status = ClassroomState.REJECTED_STATUS if student_status != ClassroomState.REJECTED_STATUS else ClassroomState.APPROVED_STATUS
                resp = self.client.put(
                    reverse('api:classroom-students-detail', kwargs={
                        'classroom_pk': classroom.id,
                        'pk': student.pk
                    }),
                    json.dumps({
                        'studentStatus': new_student_status,
                    }, cls=DjangoJSONEncoder),
                    content_type='application/json',
                )

                # Request returned success.
                self.assertIn(resp.status_code, xrange(200, 204))
                self.assertEqual(resp.data['studentStatus'], new_student_status)

                # There's still one classroom state for the classroom and user.
                self.assertEqual(ClassroomState.objects.filter(
                    classroom=classroom,
                    user=student,
                ).count(), 1)

                # revert student status:
                registration.status = student_status
                registration.save()
        
    def test_classroom_owner_can_delete_student(self):
        '''Classroom owner can DELETE a student from the classroom'''

        for classroom in Classroom.objects.all():
            self.client.force_authenticate(classroom.owner)

            for student in classroom.students.all():

                # Store the classroom state before the delete operation.
                classroom_state = ClassroomState.objects.get(
                    classroom=classroom,
                    user=student,
                )

                resp = self.client.delete(
                    reverse('api:classroom-students-detail', kwargs={
                        'classroom_pk': classroom.id,
                        'pk': student.pk
                    })
                )

                # Request returned success.
                self.assertEqual(resp.status_code, 204)

                # Check that there's no longer a classroom state instance in the DB.
                self.assertEqual(ClassroomState.objects.filter(
                    classroom=classroom,
                    user=student,
                ).count(), 0)

                # Check user object itself is not deleted:
                self.assertTrue(get_user_model().objects.filter(pk=student.pk).exists())

                # Save the classroom_state back into the DB.
                classroom_state.save()
    
    def test_classroom_student_cant_add_student(self):
        '''Student in classroom can't PUT new student in class'''

        classrooms = Classroom.objects.all().prefetch_related('students')
        all_users_ids = list(get_user_model().objects.all().values_list('id', flat=True))

        for classroom in classrooms:
            students = classroom.students.all()
            students_ids = [s.id for s in students]
            non_student_ids = list(set(all_users_ids) - set(students_ids))

            for student in students:

                self.client.force_authenticate(student)

                for user_id in non_student_ids:
                    resp = self.client.put(
                        reverse(
                            'api:classroom-students-detail',
                            kwargs={'classroom_pk': classroom.pk, 'pk': user_id}
                        ), 
                        json.dumps({}, cls=DjangoJSONEncoder), 
                        content_type='application/json'
                    )

                    self.assertEqual(resp.status_code, 403)

    def test_classroom_student_cant_delete_student(self):
        '''Student in classroom can't DELETE student from class'''
        
        classrooms = Classroom.objects.all().prefetch_related('students')
        all_users_ids = list(get_user_model().objects.all().values_list('id', flat=True))

        for classroom in classrooms:
            students = classroom.students.all()

            for me in students:
                self.client.force_authenticate(me)

                for student in students:
                    resp = self.client.delete(
                        reverse(
                            'api:classroom-students-detail',
                            kwargs={'classroom_pk': classroom.pk, 'pk': student.id}
                        ))

                    self.assertEqual(resp.status_code, 403)

    def test_random_user_cant_add_student(self):
        '''User not related to classroom can't PUT new student in class'''

        classrooms = Classroom.objects.all().prefetch_related('students')
        all_users = get_user_model().objects.all()
        all_users_ids = [u.id for u in all_users]

        for classroom in classrooms:
            students = classroom.students.all()
            students_ids = [s.id for s in students]

            non_students = list(set(all_users) - set(students))
            non_student_ids = list(set(all_users_ids) - set(students_ids))

            for me in non_students:

                if me == classroom.owner:
                    continue

                self.client.force_authenticate(me)

                for user_id in non_student_ids:

                    resp = self.client.put(
                        reverse(
                            'api:classroom-students-detail',
                            kwargs={'classroom_pk': classroom.pk, 'pk': user_id}
                        ), 
                        json.dumps({}, cls=DjangoJSONEncoder), 
                        content_type='application/json'
                    )

                    self.assertEqual(resp.status_code, 403)

    def test_random_user_cant_delete_student(self):
        '''User not related to classroom can't DELETE student from class'''

        classrooms = Classroom.objects.all().prefetch_related('students')
        all_users = get_user_model().objects.all()
        all_users_ids = [u.id for u in all_users]

        for classroom in classrooms:
            students = classroom.students.all()
            non_students = list(set(all_users) - set(students))


            for me in non_students:

                if me == classroom.owner:
                    continue

                self.client.force_authenticate(me)

                for student in students:

                    resp = self.client.delete(
                        reverse(
                            'api:classroom-students-detail',
                            kwargs={'classroom_pk': classroom.pk, 'pk': student.id}
                        ))

                    self.assertEqual(resp.status_code, 403)

    @unittest.skip('Not Implemented')
    def test_sends_email_when_child_joins_classroom(self):
        pass

    @unittest.skip('Not Implemented')
    def test_doesnt_send_email_when_non_child_joins_classroom(self):
        pass

    def test_bulk_add_students(self):
        student_statuses = ['pending', 'approved', 'rejected']

        for classroom in Classroom.objects.all():
            teacher = classroom.owner
            self.client.force_authenticate(teacher)

            #get the teacher users that are not registered to the current classroom:
            users_not_in_classroom = get_user_model().objects.filter(
                Q(pk__in=teacher.children.all()) |  #children
                Q(pk__in=ClassroomState.objects.filter(classroom__owner=teacher).values('user'))  #students in any of the teacher's classrooms
            ).exclude(
                pk__in=classroom.registrations.values('user')
            )

            #if there are users of the teacher that she can add to the classroom:
            if users_not_in_classroom.count():
                new_students_ids = [u.id for u in users_not_in_classroom]
                kwargs = [{
                    'id': stud_id,
                    'studentStatus': student_statuses[i%len(student_statuses)],  #random status from the list
                } for i,stud_id in enumerate(new_students_ids)]
                if classroom.registrations.count():
                    existing_student = classroom.registrations.first()
                    kwargs.append({
                        'id': existing_student.user_id,
                        'studentStatus': student_statuses[(student_statuses.index(existing_student.status) + 1) % len(student_statuses)],  #set to next status in the list
                    })

                resp = self.client.post(
                    reverse('api:classroom-students-list', kwargs={'classroom_pk':classroom.pk}),
                    data=json.dumps(kwargs, cls=DjangoJSONEncoder),
                    content_type='application/json',
                )
                self.assertIn(resp.status_code, xrange(200, 202))
                self.assertEqual(len(resp.data), len(kwargs))

                for reg in classroom.registrations.all():
                    for stud in resp.data:
                        if stud['id'] == reg.user_id:
                            self.assertEqual(stud['studentStatus'], reg.status)
                            break

                #test fail to add a user that is not child or student of the teacher:
                other_user = get_user_model().objects.exclude(
                    Q(pk__in=teacher.children.all()) |
                    Q(pk__in=ClassroomState.objects.filter(classroom__owner=teacher).values('user'))
                ).first()
                if other_user:
                    kwargs.append({
                        'id': other_user.id,
                        'studentStatus': student_statuses[0],
                    })
                    resp = self.client.post(
                        reverse('api:classroom-students-list', kwargs={'classroom_pk': classroom.pk}),
                        data=json.dumps(kwargs, cls=DjangoJSONEncoder),
                        content_type='application/json',
                    )
                    self.assertEqual(resp.status_code, 400)
                    self.assertEqual(len(resp.data), len(kwargs))
                    idx_fail = len(kwargs) - 1
                    for i, rdata in enumerate(resp.data):
                        if i == idx_fail:
                            self.assertIn('id', rdata)
                        else:
                            self.assertDictEqual(rdata, {})

                #remove new students added to restore db:
                classroom.registrations.filter(user__in=new_students_ids).delete()

    def test_bulk_update_students(self):
        student_statuses = ['pending', 'approved', 'rejected']

        for classroom in Classroom.objects.all():
            teacher = classroom.owner
            self.client.force_authenticate(teacher)

            if classroom.registrations.count():
                #test bulk to allow update existing students, or add students that are teacher's children or students in other classrooms:
                kwargs = [
                    {
                        'id': existing_student.user_id,
                        'studentStatus': student_statuses[(student_statuses.index(existing_student.status) + 1) % len(student_statuses)],  #set to next status in the list
                    } for existing_student in classroom.registrations.all()[:2]
                ] + [
                    {
                        'id': allowed_user.id,
                        'studentStatus': student_statuses[0],
                    } for allowed_user in get_user_model().objects.filter(
                            Q(pk__in=teacher.children.all()) |  #children
                            Q(pk__in=ClassroomState.objects.filter(classroom__owner=teacher).values('user'))  #students in any of the teacher's classrooms
                        ).exclude(
                            pk__in=classroom.registrations.values('user')
                        )[:1]
                ]

                resp = self.client.put(
                    reverse('api:classroom-students-list', kwargs={'classroom_pk': classroom.pk}),
                    data=json.dumps(kwargs, cls=DjangoJSONEncoder),
                    content_type='application/json',
                )
                self.assertEqual(resp.status_code, 200)
                self.assertEqual(len(resp.data), len(kwargs))

                for reg in classroom.registrations.all():
                    for stud in resp.data:
                        if stud['id'] == reg.user_id:
                            self.assertEqual(stud['studentStatus'], reg.status)
                            break

                #test bulk to fail when trying to add a student that is not in the teacher's children or students in other classrooms:
                fail_user = get_user_model().objects.exclude(
                    Q(pk__in=teacher.children.all()) |  #children
                    Q(pk__in=ClassroomState.objects.filter(classroom__owner=teacher).values('user'))  #students in any of the teacher's classrooms
                ).first()
                if fail_user:
                    kwargs.append({
                        'id': fail_user.id,
                        'studentStatus': student_statuses[0],
                    })
                    resp = self.client.put(
                        reverse('api:classroom-students-list', kwargs={'classroom_pk': classroom.pk}),
                        data=json.dumps(kwargs, cls=DjangoJSONEncoder),
                        content_type='application/json',
                    )
                    self.assertEqual(resp.status_code, 400)
                    self.assertEqual(len(resp.data), len(kwargs))

                    idx_fail = len(kwargs) - 1
                    for i, rdata in enumerate(resp.data):
                        if i == idx_fail:
                            self.assertIn('id', rdata)
                        else:
                            self.assertDictEqual(rdata, {})

    def test_bulk_remove_students(self):
        for classroom in Classroom.objects.all():
            teacher = classroom.owner
            self.client.force_authenticate(teacher)

            if classroom.registrations.count():
                remove_students_ids = [u.id for u in classroom.registrations.all()[:2]]
                remove_url_base = reverse('api:classroom-students-list', kwargs={'classroom_pk': classroom.pk})
                remove_url = remove_url_base + '?idList=' + ','.join([str(x) for x in remove_students_ids])
                resp = self.client.delete(
                    remove_url,
                )
                self.assertEqual(resp.status_code, 204)

                for remove_stud_id in remove_students_ids:
                    self.assertFalse(classroom.registrations.filter(user_id=remove_stud_id).exists())

                #test fail bulk remove without explicitly use idList:
                resp = self.client.delete(
                    remove_url_base,
                )
                self.assertEqual(resp.status_code, 400)

    def test_superuser_can_add_any_user(self):
        superuser = get_user_model().objects.exclude(
            Q(pk=self.classroom.owner.pk) | Q(pk__in=self.classroom.owner.guardians.all())
        ).first()
        superuser.is_superuser = True
        superuser.save()
        self.client.force_authenticate(superuser)

        non_students_users = get_user_model().objects.exclude(
            Q(pk=self.classroom.owner.pk) |  # teacher
            Q(pk__in=self.classroom.students.all()) |  # student
            Q(pk__in=superuser.children.all()) |  # child of superuser
            Q(pk__in=ClassroomState.objects.filter(classroom__owner=superuser).values('user'))  # student of superuser
        )
        for user in non_students_users:
            resp = self.client.put(
                self.get_api_details_url(user),
            )
            self.assertIn(resp.status_code, xrange(200, 202))
            self.assertTrue(self.classroom.students.filter(pk=user.pk).exists())
