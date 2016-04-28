import json
import copy

from django.db.models import Q, F, Count
from django.test import override_settings
from django.core.urlresolvers import reverse
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.auth import get_user_model
from django.core import management

from rest_framework.test import APITestCase as DRFTestCase

from common_project_classroom_tests import ClassroomProjectTestsBase
from edu_api_test_case import EduApiTestCase

from api_test_case.decorators import should_check_action

from ..serializers import ClassroomSerializer
from ..models import (
    Project,
    Classroom,
    ProjectInClassroom,
    IgniteUser,
    ClassroomState,
)

@override_settings(DISABLE_SENDING_CELERY_EMAILS=True)
class ClassroomTests(ClassroomProjectTestsBase, EduApiTestCase, DRFTestCase):
    '''
    Tests the Classroom API.
    '''

    fixtures = ['test_projects_fixture_1.json']
    model = Classroom

    # Specific configuration for common_project_classroom_tests
    embedded_model = Project
    embedded_obj_s = 'project'
    embedded_obj_p = 'projects'
    embedded_list_ids = 'projectsIds'
    embedded_through_model = ProjectInClassroom

    def get_all_user_objects(self):
        user = self.global_user.first()

        return Classroom.objects.filter(
            Q(owner=user) | Q(owner__in=user.children.all()) |
            Q(id__in=user.classrooms.values_list('id', flat=True))
        ).order_by('id')

    def api_test_init(self):
        super(ClassroomTests, self).api_test_init()

        self.put_actions = [
            # Successful PUT
            {
                'get_object': lambda: Classroom.objects.exclude(title='1111111').filter(owner=self.global_user).first(),
                'updated_data': {'title': '1111111'},
            }, 
            # Not owner and not student
            {
                'user': get_user_model().objects.get(id=4),
                'get_object': lambda: Classroom.objects.exclude(
                    owner_id=4
                ).exclude(
                    id__in=get_user_model().objects.get(id=4).classrooms.values_list('id', flat=True)
                )[0],
                'expected_result': 404,
            }, 
            # Not owner but is student.
            {
                'user': get_user_model().objects.get(id=4),
                'get_object': lambda: Classroom.objects.filter(
                    id__in=get_user_model().objects.get(id=4).classrooms.values_list('id', flat=True)
                ).exclude(
                    owner_id=4
                )[0],
                'expected_result': 403,
            }, 
            # Not Authorized
            {
                'user': None,
                'get_object': lambda: Classroom.objects.all()[0],
                'expected_result': 401,
            }
        ]
        self.invalid_objects_patch = {
            'user': get_user_model().objects.get(id=4),
            'get_object': lambda: Classroom.objects.filter(owner_id=4)[0],
            'invalid_patches': [{
                'data': {'bannerImage': 'http://test.com/invalid/'+'abcdefghij'*52+'.jpg',},
            }, {
                'data': {'cardImage': 'http://test.com/invalid/'+'abcdefghij'*52+'.jpg',}
            }],
        }
        self.global_user = get_user_model().objects.filter(id=2)
        self.api_list_url = reverse('api:classroom-list')
        self.api_details_url = 'api:classroom-detail'
        self.non_existant_obj_details_url = reverse('api:classroom-detail', kwargs={'pk': 4444})

        # There are no public objects.
        self.all_public_objects = Classroom.objects.none()
        self.allow_unauthenticated_get = False
        self.serializer = ClassroomSerializer
        self.sort_key = 'id'
        self.filters = [
            ({'author__id': 4}, {'owner__id': 4},),
            ({'idList': '2,3,a,,,15'}, 'ERROR',),
            ({'idList': '2'}, {'id__in': [2]},),
            ({'idList': 'a,b'}, 'ERROR',),
            ({'idList': ''}, 'ERROR',),
            ({'numberOfProjects__gt': 1}, {'projects_count__gt': 1}),
            ({'numberOfStudents__gte': 1}, {'students_approved_count__gte': 1}),
        ]
        self.pagination = True
        self.free_text_fields = ['title', 'description',]

    def setUp(self):
        super(ClassroomTests, self).setUp()

        # Make sure data you read from DB is reset before each test:
        self.object_to_post = {
            'title': 'Testing 101',
            'description': 'Learn how to test Django applications using Python\'s unittest',
            'bannerImage': 'http://placekitten.com/2048/640/',
            'cardImage': 'http://placekitten.com/1024/768/',
        }
        self.object_to_post_with_projects = copy.copy(self.object_to_post)
        self.object_to_post_with_projects.update({
            'projectsIds': list(Project.objects.filter(publish_mode=Project.PUBLISH_MODE_PUBLISHED, lock=0).values_list('id', flat=True)[:3]),
        })
        self.field_to_put = {'field': 'title', 'value': 'Testing 102'}
        self.field_to_patch = {'field': 'title', 'value': 'Testing 103', 'exclude': 'description'}
        self.dropfields = ['projectsIds', 'projects']

    def test_can_access_classrooms_only_if_owner_or_student_or_studentguardian(self):
        '''
        Check that users who are not the classroom owners or 
        students in the classroom can't see it.
        '''

        #pick a classroom with owner, students and guardians that each has unique user
        classroom = Classroom.objects.all().filter(
            ~Q(owner_id=F('students__id')) &
            ~Q(owner_id=F('students__guardians__id')) &
            ~Q(students__id=F('students__guardians__id'))
        ).first()
        classroom_owner_id = classroom.owner_id
        classroom_students_ids = list(classroom.students.values_list('id', flat=True))
        classroom_students_guardians_ids = list(IgniteUser.objects.filter(children__id__in=classroom_students_ids).values_list('id', flat=True))
        classroom_count = Classroom.objects.all().count()

        # Non-owner, non-student, non-student-guardian
        # ############################################

        user = get_user_model().objects.exclude(
            id__in=[classroom_owner_id,] + classroom_students_ids + classroom_students_guardians_ids,
        ).first()
        self.client.force_authenticate(user)

        # Details
        resp = self.client.get(reverse('api:classroom-detail', kwargs={'pk': classroom.id}))
        self.assertEqual(resp.status_code, 404)
        
        # List
        resp = self.client.get(
            reverse('api:classroom-list') + 
            '?pageSize=' + str(classroom_count) +
            '&fields=id'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(classroom.id, [x['id'] for x in resp.data['results']])

        # Owner, non-student, non-student-guardian
        # ########################################

        self.client.force_authenticate(classroom.owner)
        self.assertNotIn(classroom.owner, classroom.students.all())

        # Details
        resp = self.client.get(reverse('api:classroom-detail', kwargs={'pk': classroom.id}))
        self.assertEqual(resp.status_code, 200)
        
        # List
        resp = self.client.get(
            reverse('api:classroom-list') + 
            '?pageSize=' + str(classroom_count) +
            '&fields=id'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(classroom.id, [x['id'] for x in resp.data['results']])

        # Non-owner, student, non-student-guardian
        # ########################################

        user = get_user_model().objects.filter(
            id__in=classroom_students_ids
        ).exclude(
            id=classroom.owner_id,
        ).exclude(
            id__in=classroom_students_guardians_ids,
        ).first()
        self.client.force_authenticate(user)

        # Details
        resp = self.client.get(reverse('api:classroom-detail', kwargs={'pk': classroom.id}))
        self.assertEqual(resp.status_code, 200)
        
        # List
        resp = self.client.get(
            reverse('api:classroom-list') + 
            '?pageSize=' + str(classroom_count) +
            '&fields=id'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(classroom.id, [x['id'] for x in resp.data['results']])

        # Non-owner, non-student, student-guardian
        # ########################################

        user = get_user_model().objects.filter(
            id__in=classroom_students_guardians_ids
        ).exclude(
            id=classroom.owner_id,
        ).exclude(
            id__in=classroom_students_ids,
        ).first()
        self.client.force_authenticate(user)

        # Details
        resp = self.client.get(reverse('api:classroom-detail', kwargs={'pk': classroom.id}))
        self.assertEqual(resp.status_code, 200)

        # List (not accessible without ?include=children query param)
        resp = self.client.get(
            reverse('api:classroom-list') +
            '?pageSize=' + str(classroom_count) +
            '&fields=id'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(classroom.id, [x['id'] for x in resp.data['results']])

        #List (accessible with ?include=children query param)
        resp = self.client.get(
            reverse('api:classroom-list') +
            '?pageSize=' + str(classroom_count) +
            '&fields=id' +
            '&include=children'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(classroom.id, [x['id'] for x in resp.data['results']])

    def test_cant_access_classroom_if_not_approved_student_or_guardian_of_not_approved_student(self):
        '''
        Check that students that are not approved or guardians of students that are not approved,
        can't see the classroom.
        '''

        #pick a classroom with owner, students and guardians that each has unique user
        classroom = Classroom.objects.all().filter(
            ~Q(owner_id=F('students__id')) &
            ~Q(owner_id=F('students__guardians__id')) &
            ~Q(students__id=F('students__guardians__id'))
        ).first()
        classroom_owner_id = classroom.owner_id
        classroom_students_ids = list(classroom.students.values_list('id', flat=True))
        classroom_students_guardians_ids = list(IgniteUser.objects.filter(children__id__in=classroom_students_ids).values_list('id', flat=True))
        classroom_count = Classroom.objects.all().count()

        # Non-owner, non-student, non-student-guardian
        # ############################################

        user = get_user_model().objects.exclude(
            id__in=[classroom_owner_id,] + classroom_students_ids + classroom_students_guardians_ids,
        ).first()
        self.client.force_authenticate(user)

        # Details
        resp = self.client.get(reverse('api:classroom-detail', kwargs={'pk': classroom.id}))
        self.assertEqual(resp.status_code, 404)

        # List
        resp = self.client.get(
            reverse('api:classroom-list') +
            '?pageSize=' + str(classroom_count) +
            '&fields=id'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(classroom.id, [x['id'] for x in resp.data['results']])


    def test_put_embedded_without_attribute_list_not_affected(self):
        '''
        Tests that when embedded attribute is omitted, list is not affected
        '''

        # Get a list with at least 3 items.
        obj = self.get_list_with_min_size(3, for_edit=True)[0]

        list_len = getattr(obj, self.embedded_obj_p).all().count()
        self.assertGreaterEqual(list_len, 3)

        resp = self.client.get(reverse(self.api_details_url, kwargs={'pk': obj.id}), {'embed': self.embedded_list_ids})

        # remove embedded attribute:
        del resp.data[self.embedded_list_ids]

        resp1 = self.client.put(
            resp.data['self'] + '?embed=%s'%self.embedded_list_ids,
            json.dumps(resp.data, cls=DjangoJSONEncoder),
            content_type='application/json'
        )

        self.assertIn(resp1.status_code, range(200, 205))

        obj_after = (self.all_user_objects_for_edit if self.all_user_objects_for_edit else self.all_user_objects).get(id=obj.id)

        list_len_after = getattr(obj_after, self.embedded_obj_p).all().count()
        self.assertGreaterEqual(list_len_after, 3)
        self.assertEqual(list_len, list_len_after)
        self.assertListEqual(
            list(getattr(obj, self.embedded_obj_p).all()),
            list(getattr(obj_after, self.embedded_obj_p).all())
        )

        self.assertListEqual(
            resp1.data[self.embedded_list_ids],
            list(obj_after.projects_through_set.values_list('project_id', flat=True))
        )


    @should_check_action(actions_tested=('update',))
    def test_cant_have_classroom_with_unpublished_projects(self):

        object_to_publish = copy.deepcopy(self.object_to_post_with_projects)

        resp = self.client.post(
            self.api_list_url + '?embed=%s' % ','.join([self.embedded_list_ids]),
            json.dumps(object_to_publish, cls=DjangoJSONEncoder),
            content_type='application/json',
        )

        self.assertIn(resp.status_code, xrange(200,205))

        api_obj = resp.data
        api_obj['projectsIds'].insert(2, Project.objects.exclude(
                publish_mode=Project.PUBLISH_MODE_PUBLISHED
            ).values_list('id', flat=True)[0])
        api_obj_patch = {
            'projectsIds': api_obj['projectsIds'],
        }

        resp2 = self.client.put(
            api_obj['self'] + '?embed=%s' % ','.join([self.embedded_list_ids]),
            json.dumps(api_obj, cls=DjangoJSONEncoder),
            content_type='application/json',
        )

        self.assertEqual(resp2.status_code, 400)
        self.assertIn('projectsIds', resp2.data)

        resp3 = self.client.patch(
            api_obj['self'] + '?embed=%s' % ','.join([self.embedded_list_ids]),
            json.dumps(api_obj_patch, cls=DjangoJSONEncoder),
            content_type='application/json',
        )

        self.assertEqual(resp3.status_code, 400)
        self.assertIn('projectsIds', resp3.data)

    def test_child_cannot_create_classroom(self):
        child_user = get_user_model().objects.filter(is_child=True).first()
        if not child_user:
            return

        self.client.force_authenticate(child_user)

        object_to_post = copy.deepcopy(self.object_to_post_with_projects)
        resp = self.client.post(
            self.api_list_url,
            json.dumps(object_to_post, cls=DjangoJSONEncoder),
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 403)

    def test_classroom_created_with_initial_classroom_code(self):
        '''Test that when creating a classroom, it has initial classroom code.'''
        #test Classroom object model initializes with code:
        self.assertIsNotNone(Classroom().code)
        self.assertEqual(Classroom(code=None).code, None)
        self.assertEqual(Classroom(code='ABCDEFGH').code, 'ABCDEFGH')

        #test creating classroom has code:
        self.client.force_authenticate(self.global_user)
        resp = self.client.post(
            self.api_list_url,
            data=json.dumps(self.object_to_post, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 201)
        resp2 = self.client.get(
            reverse('api:classroom-code-generator-detail', kwargs={'classroom_pk': resp.data['id']})
        )
        self.assertEqual(resp2.status_code, 200)
        self.assertIsNotNone(resp2.data['code'])

    def test_access_classroom_code_generator_only_by_teacher(self):
        '''Can access to classroom code generator only if teacher of the classroom'''
        classroom = Classroom.objects.annotate(num_of_students=Count('students')).filter(num_of_students__gte=1).first()
        classroom.code = classroom.generate_code()
        classroom.save()
        classroom_code = classroom.code
        classroom_code_generator_url = reverse('api:classroom-code-generator-detail', kwargs={'classroom_pk': classroom.pk})

        #annonymous user:
        self.client.force_authenticate(None)
        resp = self.client.get(classroom_code_generator_url)
        self.assertEqual(resp.status_code, 401)
        resp = self.client.post(classroom_code_generator_url)
        self.assertEqual(resp.status_code, 401)
        resp = self.client.delete(classroom_code_generator_url)
        self.assertEqual(resp.status_code, 401)

        #student user:
        self.client.force_authenticate(classroom.students.first())
        resp = self.client.get(classroom_code_generator_url)
        self.assertEqual(resp.status_code, 403)
        resp = self.client.post(classroom_code_generator_url)
        self.assertEqual(resp.status_code, 403)
        resp = self.client.delete(classroom_code_generator_url)
        self.assertEqual(resp.status_code, 403)

        #teacher user:
        self.client.force_authenticate(classroom.owner)

        #get classroom code:
        resp = self.client.get(classroom_code_generator_url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['code'], classroom_code)

        #generate new classroom code:
        for i in xrange(0, 5):
            resp = self.client.post(classroom_code_generator_url)
            self.assertIn(resp.status_code, xrange(200, 202))
            self.assertNotEqual(resp.data['code'], classroom_code)
            classroom_code = resp.data['code']

        #delete classroom code:
        resp = self.client.delete(classroom_code_generator_url)
        self.assertIn(resp.status_code, xrange(200, 205))
        self.assertEqual(resp.data['code'], None)

    def test_authenticated_user_can_access_and_join_classroom_by_code(self):
        '''Authenticated user can access a classroom by code'''
        classroom = Classroom.objects.first()
        classroom.code = classroom.generate_code()
        classroom.save()
        classroom_code_url = reverse('api:classroom-code-detail', kwargs={'classroom_code': classroom.code})
        classroom_code_state_url = reverse('api:classroom-code-state-detail', kwargs={'classroom_code': classroom.code})

        #annonymouse user - allow access only for classroom code:
        self.client.force_authenticate(None)
        resp = self.client.get(classroom_code_url)
        self.assertEqual(resp.status_code, 200)
        resp = self.client.get(classroom_code_state_url)
        self.assertEqual(resp.status_code, 401)
        resp = self.client.post(classroom_code_state_url)
        self.assertEqual(resp.status_code, 401)
        resp = self.client.put(classroom_code_state_url)
        self.assertEqual(resp.status_code, 401)

        #authenticated user - allow access:
        user = get_user_model().objects.exclude(
            Q(pk=classroom.owner.pk) | Q(pk__in=classroom.students.all())
        ).first()
        self.client.force_authenticate(user)

        resp = self.client.get(classroom_code_url)
        self.assertEqual(resp.status_code, 200)
        for f in ['id', 'self', 'title', 'author', 'description', 'bannerImage', 'cardImage', 'joinUrl']:
            self.assertIn(f, resp.data)
        self.assertIn('oxygenId', resp.data['author'])
        join_url = resp.data['joinUrl']
        self.assertTrue(join_url.endswith(classroom_code_state_url))

        #assert classroom state does not exist for the user:
        resp2 = self.client.get(join_url)
        self.assertEqual(resp2.status_code, 404)

        #join classroom via joinUrl field in pending status:
        resp3 = self.client.post(join_url)
        self.assertIn(resp3.status_code, xrange(200, 202))
        self.assertEqual(resp3.data['userId'], user.id)
        self.assertEqual(resp3.data['status'], ClassroomState.PENDING_STATUS)
        self.assertEqual(ClassroomState.objects.get(classroom=classroom, user=user).status, ClassroomState.PENDING_STATUS)
        self.assertIn(user, classroom.students.all())

        #check cannot change status by code:
        resp4 = self.client.put(
            join_url,
            data=json.dumps({'status': ClassroomState.APPROVED_STATUS}, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertIn(resp4.status_code, xrange(200, 202))
        self.assertEqual(resp4.data['userId'], user.id)
        self.assertEqual(resp4.data['status'], ClassroomState.PENDING_STATUS)

    def test_teacher_can_access_but_not_join_classroom_by_code(self):
        '''Authenticated user can access a classroom by code'''
        classroom = Classroom.objects.first()
        classroom.code = classroom.generate_code()
        classroom.save()
        classroom_code_url = reverse('api:classroom-code-detail', kwargs={'classroom_code': classroom.code})
        classroom_code_state_url = reverse('api:classroom-code-state-detail', kwargs={'classroom_code': classroom.code})
        teacher = classroom.owner

        #teacher - allow access:
        self.client.force_authenticate(teacher)
        resp = self.client.get(classroom_code_url)
        self.assertEqual(resp.status_code, 200)
        join_url = resp.data['joinUrl']
        self.assertTrue(join_url.endswith(classroom_code_state_url))

        #assert classroom state does not exist for the user:
        resp2 = self.client.get(join_url)
        self.assertEqual(resp2.status_code, 404)

        #check teacher fails to join her own classroom:
        resp3 = self.client.post(join_url)
        self.assertEqual(resp3.status_code, 403)
        self.assertNotIn(teacher, classroom.students.all())

    def test_not_approved_student_cannot_access_classroom(self):
        '''Not approved student cannot access the classroom regulary without a code'''
        classroom = Classroom.objects.first()
        classroom_url = reverse('api:classroom-detail', kwargs={'pk': classroom.pk})

        user = get_user_model().objects.exclude(
            Q(pk=classroom.owner.pk) | Q(pk__in=classroom.students.all())
        ).first()
        self.client.force_authenticate(user)

        #pending - deny access:
        user_classroom_state = ClassroomState(
            user=user,
            classroom=classroom,
            status=ClassroomState.PENDING_STATUS,
        )
        user_classroom_state.save()
        resp = self.client.get(classroom_url)
        self.assertEqual(resp.status_code, 404)

        #rejected - deny access:
        user_classroom_state.status = ClassroomState.REJECTED_STATUS
        user_classroom_state.save()
        resp = self.client.get(classroom_url)
        self.assertEqual(resp.status_code, 404)

        #approved - allow access:
        user_classroom_state.status = ClassroomState.APPROVED_STATUS
        user_classroom_state.save()
        resp = self.client.get(classroom_url)
        self.assertEqual(resp.status_code, 200)

    def test_approved_student_will_not_become_pending_when_post_state_by_code(self):
        '''Approved student that accesses the classroom by code and POST state will stay approved'''
        approved_classroom_state = ClassroomState.objects.filter(status=ClassroomState.APPROVED_STATUS).first()
        classroom = approved_classroom_state.classroom
        classroom.code = classroom.generate_code()
        classroom.save()
        classroom_code_state_url = reverse('api:classroom-code-state-detail', kwargs={'classroom_code': classroom.code})

        student = approved_classroom_state.user
        self.client.force_authenticate(student)

        resp = self.client.get(classroom_code_state_url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], ClassroomState.APPROVED_STATUS)

        resp2 = self.client.post(classroom_code_state_url)
        self.assertIn(resp2.status_code, xrange(200, 202))
        self.assertEqual(resp2.data['status'], ClassroomState.APPROVED_STATUS)
        self.assertEqual(ClassroomState.objects.get(classroom=classroom, user=student).status, ClassroomState.APPROVED_STATUS)

    def test_rejected_student_can_join_again_or_delete_by_code(self):
        '''Rejected student that accesses the classroom by code and POST state will re-join the classroom in pending status again'''
        classroom = Classroom.objects.first()
        classroom.code = classroom.generate_code()
        classroom.save()
        classroom_code_state_url = reverse('api:classroom-code-state-detail', kwargs={'classroom_code': classroom.code})

        user = get_user_model().objects.exclude(
            Q(pk=classroom.owner.pk) | Q(pk__in=classroom.students.all())
        ).first()
        self.client.force_authenticate(user)

        user_classroom_state = ClassroomState(
            user=user,
            classroom=classroom,
            status=ClassroomState.REJECTED_STATUS,
        )
        user_classroom_state.save()

        resp = self.client.get(classroom_code_state_url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], ClassroomState.REJECTED_STATUS)

        resp2 = self.client.post(classroom_code_state_url)
        self.assertIn(resp2.status_code, xrange(200, 202))
        self.assertEqual(resp2.data['status'], ClassroomState.PENDING_STATUS)
        self.assertEqual(ClassroomState.objects.get(classroom=classroom, user=user).status, ClassroomState.PENDING_STATUS)

        resp3 = self.client.delete(classroom_code_state_url)
        self.assertIn(resp3.status_code, xrange(200, 205))
        resp4 = self.client.get(classroom_code_state_url)
        self.assertEqual(resp4.status_code, 404)

    def test_teacher_can_send_invites_to_emails_with_classroom_code_to_join(self):
        '''Teacher can send invitations to emails addresses with classroom code to join'''
        classroom = Classroom.objects.first()
        classroom_code_invite_url = reverse('api:classroom-code-invite-list', kwargs={'classroom_pk': classroom.pk})

        post_kwargs = {
            'data': json.dumps({
                'message': 'Join to my classroom',
                'invitees': [
                    't1@test.com',
                    't2@test.com',
                ]
            }, cls=DjangoJSONEncoder),
            'content_type': 'application/json',
        }

        #send with no code - fail:
        classroom.code = None
        classroom.save()
        resp = self.client.post(
            classroom_code_invite_url,
            **post_kwargs
        )
        self.assertEqual(resp.status_code, 403)

        #send with code - success:
        classroom.code = classroom.generate_code()
        classroom.save()
        resp = self.client.post(
            classroom_code_invite_url,
            **post_kwargs
        )
        self.assertIn(resp.status_code, xrange(200, 203))

    def test_classroom_counters(self):
        """
        Make sure the classroom counters are correct.
        """
        #build counters:
        management.call_command('rebuild_counters')

        self.client.force_authenticate(self.global_user)
        data = self.client.get(self.api_list_url).data['results']

        for classroom_data in data:
            classroom_obj = Classroom.objects.get(id=classroom_data['id'])
            self.assertEqual(classroom_data['numberOfProjects'], classroom_obj.projects.count())
            self.assertEqual(classroom_data['numberOfStudents'], classroom_obj.registrations.count())


    def test_superuser_can_get_all_classrooms(self):
        superuser = get_user_model().objects.first()
        superuser.is_superuser = True
        superuser.save()
        self.client.force_authenticate(superuser)

        self.assertGreater(
            Classroom.objects.count(),
            Classroom.objects.filter(Q(owner=superuser) | Q(students=superuser)).count(),
            msg='Make sure there is a classroom a superuser is not owner or enrolled to.'
        )

        resp = self.client.get(self.api_list_url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(int(resp.data['count']), Classroom.objects.count())

    def test_classrooms_list_archived(self):
        user = self.global_user
        user_all_classrooms = self.all_user_objects
        self.assertEqual(user_all_classrooms.count(), user_all_classrooms.filter(is_archived=False).count(), msg='Assumed starting when no classroom is archived.')
        self.client.force_authenticate(user)

        num_user_all_classrooms = user_all_classrooms.count()

        resp = self.client.get(self.api_list_url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], num_user_all_classrooms)

        # archive user classroom
        archive_classroom = user.authored_classrooms.filter(is_archived=False).all()[0]
        resp = self.client.patch(
            reverse(self.api_details_url, kwargs={'pk': archive_classroom.pk}),
            data=json.dumps({
                'isArchived': True
            }, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['isArchived'], True)
        archive_classroom = Classroom.objects.get(pk=archive_classroom.pk)
        self.assertEqual(archive_classroom.is_archived, True)

        # GET /classrooms/
        user_all_classrooms_default_list = user_all_classrooms.filter(Q(owner=user) | Q(is_archived=False))
        resp = self.client.get(self.api_list_url, {'pageSize': num_user_all_classrooms})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], user_all_classrooms_default_list.count())
        self.assertSetEqual(
            set([x['id'] for x in resp.data['results']]),
            set([x.id for x in user_all_classrooms_default_list])
        )

        # GET /classrooms/?isArchived=false
        resp = self.client.get(self.api_list_url, {'pageSize': num_user_all_classrooms, 'isArchived': 'false'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], num_user_all_classrooms-1)
        self.assertSetEqual(
            set([x['id'] for x in resp.data['results']]),
            set([x.id for x in user_all_classrooms.filter(is_archived=False)])
        )

        # GET /classrooms/?isArchived=true
        resp = self.client.get(self.api_list_url, {'pageSize': num_user_all_classrooms, 'isArchived': 'true'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)
        self.assertSetEqual(
            set([x['id'] for x in resp.data['results']]),
            set([x.id for x in user_all_classrooms.filter(is_archived=True)])
        )

        # GET /classrooms/?include=archived
        resp = self.client.get(self.api_list_url, {'pageSize': num_user_all_classrooms, 'include': 'archived'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], num_user_all_classrooms)
        self.assertSetEqual(
            set([x['id'] for x in resp.data['results']]),
            set([x.id for x in user_all_classrooms.all()])
        )

    def test_classroom_projects_separators(self):
        classroom = Classroom.objects.annotate(
            num_projects=Count('projects'),
        ).order_by(
            '-num_projects',
        )[0]
        classroom_num_projects = classroom.projects.count()
        classroom_api_details_url = reverse(self.api_details_url, kwargs={'pk': classroom.id})

        def _check_invalid_projects_separators(projects_separators):
            resp = self.client.patch(
                classroom_api_details_url,
                data=json.dumps({
                    'projectsSeparators': projects_separators,
                }, cls=DjangoJSONEncoder),
                content_type='application/json',
            )
            self.assertEqual(resp.status_code, 400)
            self.assertIn('projectsSeparators', resp.data)

        def _check_valid_projects_separators(projects_separators):
            resp = self.client.patch(
                classroom_api_details_url,
                data=json.dumps({
                    'projectsSeparators': projects_separators,
                }, cls=DjangoJSONEncoder),
                content_type='application/json',
            )
            self.assertEqual(resp.status_code, 200)
            self.assertListEqual(resp.data['projectsSeparators'], projects_separators)

        _check_invalid_projects_separators([
            {'before': -1, 'label': 'Choose one of the following projects'},  #before is negative
        ])
        _check_invalid_projects_separators([
            {'before': classroom_num_projects, 'label': 'Choose one of the following projects'},  #before is over number of projects
        ])
        _check_invalid_projects_separators([
            {'before': 0, 'label': ''},  #label is empty
        ])
        _check_invalid_projects_separators([
            {'before': -1, 'label': '* Too Long Label *' * 15},  # label >140
        ])

        _check_valid_projects_separators([
            {'before': 0, 'label': 'Choose one of the following projects'},
            {'before': 0, 'label': 'Choose one of the following projects'},  #same label in the same order
            {'before': classroom_num_projects-1, 'label': 'Choose one of the following projects'},
            {'before': int(classroom_num_projects/2), 'label': 'Choose one of the following projects'},
        ])

        # Create classroom with no projects, should throw error when inserting projects separators
        obj_to_post = copy.deepcopy(self.object_to_post)
        obj_to_post.update({
            'projectsSeparators': [
                {'before': 0, 'label': 'Separator when no project exists!'},
            ],
        })
        resp = self.client.post(
            self.api_list_url,
            data=json.dumps(obj_to_post),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('projectsSeparators', resp.data)
