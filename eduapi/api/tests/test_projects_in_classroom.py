import json
from django.core.urlresolvers import reverse
from django.core.serializers.json import DjangoJSONEncoder

from api.tests import test_projects
from ..serializers import ProjectWithOrderSerializer
from ..models import Project, Classroom, ProjectInClassroom
from ..auth.models import IgniteUser

class ProjectsInClassroomsTests(test_projects.ProjectTests):

    fixtures = ['test_projects_fixture_1.json']

    def api_test_init(self):
        super(ProjectsInClassroomsTests, self).api_test_init()

        self.classroom_id = 1

        self.put_actions = []

        self.actions = ('list', 'retrieve',)

        self.api_list_url = reverse('api:classroom-project-list', kwargs={'classroom_pk': self.classroom_id})
        self.non_existant_obj_details_url = reverse('api:classroom-project-detail', kwargs={'classroom_pk': self.classroom_id, 'pk': 4444})

        self.allow_unauthenticated_get = False
        self.serializer = ProjectWithOrderSerializer
        self.sort_key = 'id'

        # Can't filter nested objects, that's why DB filters are empty
        self.filters = [
            ({'age': Project.AGES[0][0]}, None,),
            ({'difficulty': 'easy', 'duration__gte': 10}, None,),
            ({'author__id': 4}, {'owner__id': 4},),
        ]
        self.pagination = True
        self.free_text_fields = ['title', 'description', 'teacher_additional_resources', ]
        self.project_object_to_add = self.object_to_post
        self.object_to_post = None
        self.dropfields = ['lessonsIds', 'lessons', 'state', 'enrolled', 'draft', 'origin', 'forceEditFrom',
                           'teacherInfo', 'teacher_additional_resources', 'teachers_files_list', 'prerequisites',
                           'teacher_tips', 'ngss', 'ccss', 'subject', 'grades_range', 'technology',
                           'four_cs_creativity', 'four_cs_critical', 'four_cs_communication', 'four_cs_collaboration',
                           'skills_acquired', 'learning_objectives',]

        # Some tests in ProjectTests run for all of the users. This 
        # list is a hook that enables us to supply a different list 
        # for "all users with GET permissions".
        self.users_with_get_permission = Classroom.objects.get(
            id=self.classroom_id
        ).students.all()

    def get_api_details_url(self, obj):
        return reverse(
            'api:classroom-project-detail',
            kwargs={
                'classroom_pk': self.classroom_id,
                'pk': obj.pk
            }
        )

    def setUp(self):

        super(ProjectsInClassroomsTests, self).setUp()

        self.classroom_obj = Classroom.objects.get(id=self.classroom_id)

        self.all_user_objects = self.classroom_obj.projects.all()
        self.all_public_objects = self.all_user_objects

        self.classroom_students = self.classroom_obj.students.all()


    def test_get_list_everyone_can(self):
        '''Overriding ApiTestCase's default implementation. User can't get list of students if not logged in'''

        self.client.force_authenticate(None)
        resp = self.client.get(self.api_list_url + '?pageSize=' + str(self.all_user_objects.count()))
        self.assertEqual(resp.status_code, 401)

    def test_student_can_get_list(self):
        '''
        Student can get list of projects in his classroom.
        '''
        self.client.force_authenticate(user=self.classroom_students[0])
        self.test_get_list(self.api_list_url, self.all_user_objects)

    def test_logged_in_not_student_can_not_get_list(self):
        '''
        Logged in user cannot get list of projects in a classroom that he is not a student of.
        '''
        student = None
        for x in IgniteUser.objects.all():
            if x not in self.classroom_students and x.id != self.classroom_obj.owner.id:
                student = x
                break
        if not student:
            return
        self.client.force_authenticate(user=student)
        resp = self.client.get(self.api_list_url + '?pageSize=' + str(self.all_user_objects.count()))
        self.assertEqual(resp.status_code, 403)

    def test_student_get_choices_on_options(self):
        '''
        Student can get choices in options for projects in his classroom.
        '''
        self.client.force_authenticate(user=self.classroom_students[0])
        resp = self.client.options(self.api_list_url)
        self.check_choices_on_options_response(self.choice_fields, resp)

    def test_logged_in_not_student_can_not_get_choices_on_options(self):
        '''
        Logged in user cannot get projects in options for lessons in a classroom that he is not a student of.
        '''
        student = None
        for x in IgniteUser.objects.all():
            if x not in self.classroom_students and x.id != self.classroom_obj.owner.id:
                student = x
                break
        if not student:
            return
        self.client.force_authenticate(user=student)
        resp = self.client.options(self.api_list_url)
        self.assertEqual(resp.status_code, 403)

    def test_student_can_get_project_in_classroom(self):
        '''Student can get project in his classroom'''
        project_in_classroom = self.all_user_objects[0] if len(self.all_user_objects) else None
        self.client.force_authenticate(user=self.classroom_students[0])
        resp = self.client.get(self.get_api_details_url(project_in_classroom))
        self.assertEqual(resp.status_code, 200)

    def test_student_can_not_get_project_not_in_classroom(self):
        '''Student cannot get project that is not in his classroom'''
        project_not_in_classroom = Project.objects.exclude(id__in=self.all_user_objects).all()[0]
        self.client.force_authenticate(user=self.classroom_students[0])
        resp = self.client.get(self.get_api_details_url(project_not_in_classroom))
        self.assertEqual(resp.status_code, 404)

    def test_can_not_get_project_in_unauthorized_classroom(self):
        '''Not student User can not get project in a classroom that is not his'''
        project_in_classroom = self.all_user_objects[0] if len(self.all_user_objects) else None
        student = None
        for x in IgniteUser.objects.all():
            if x not in self.classroom_students and x.id != self.classroom_obj.owner.id:
                student = x
                break
        if not student:
            return
        self.client.force_authenticate(user=student)
        resp = self.client.get(self.get_api_details_url(project_in_classroom))
        self.assertEqual(resp.status_code, 403)

    def test_everyone_can_get_details(self):
        '''Overriding ApiTestCase's default implementation: Anonymous user can not get project in a classroom'''
        project_in_classroom = self.all_user_objects[0] if len(self.all_user_objects) else None
        self.client.force_authenticate(None)
        resp = self.client.get(self.get_api_details_url(project_in_classroom))
        self.assertEqual(resp.status_code, 401)

    def test_disabled_unsafe_methods_for_project_in_classroom_api(self):
        """Check that unsafe methods (POST, PUT, PATCH, DELETE) are not allowed for api:classroom-project-list/detail views."""
        resp = self.client.post(self.api_list_url)
        self.assertEqual(resp.status_code, 405)
        api_details_url = self.get_api_details_url(self.classroom_obj.projects.all()[0])
        resp = self.client.patch(api_details_url)
        self.assertEqual(resp.status_code, 405)

    def test_put_and_delete_project_in_classroom(self):
        """Checks that can put project in classroom in desired order via /classrooms/:id/projects/:id/ and delete it"""
        #create unpublished project to add to classroom
        new_project_resp = self._get_new_project_with_lessons()
        project_to_add = Project.objects.get(id=new_project_resp.data['id'])
        if not project_to_add:
            return
        api_project_in_classroom_url = reverse('api:classroom-project-detail', kwargs={'classroom_pk': self.classroom_obj.pk, 'pk': project_to_add.pk})

        # PUT - not classroom owner - denied:
        self.client.force_authenticate(self.classroom_students[0])
        resp = self.client.get(api_project_in_classroom_url)
        self.assertEqual(resp.status_code, 404)
        resp1 = self.client.put(
            api_project_in_classroom_url,
            json.dumps({'order': 0}, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp1.status_code, 403)

        # PUT - classroom owner - allowed:
        self.client.force_authenticate(self.global_user)
        resp = self.client.get(api_project_in_classroom_url)
        self.assertEqual(resp.status_code, 404)
        # unpublished project:
        project_to_add.publish_mode = Project.PUBLISH_MODE_EDIT
        project_to_add.save()
        resp1 = self.client.put(
            api_project_in_classroom_url,
            json.dumps({'order': 0}, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertEqual(resp1.status_code, 403)
        # published project:
        project_to_add.publish_mode = Project.PUBLISH_MODE_PUBLISHED
        project_to_add.save()
        resp2 = self.client.put(
            api_project_in_classroom_url,
            json.dumps({'order': 0}, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        self.assertIn(resp2.status_code, xrange(200, 202))
        self.assertIn(project_to_add, self.classroom_obj.projects.all())
        self.assertEqual(0, ProjectInClassroom.objects.get(classroom=self.classroom_obj, project=project_to_add).order)

        # DELETE - not classroom owner - denied:
        self.client.force_authenticate(self.classroom_students[0])
        resp = self.client.delete(api_project_in_classroom_url)
        self.assertEqual(resp.status_code, 403)

        # DELETE - classroom owner - allowed:
        self.client.force_authenticate(self.global_user)
        resp = self.client.delete(api_project_in_classroom_url)
        self.assertEqual(resp.status_code, 204)
        resp = self.client.get(api_project_in_classroom_url)
        self.assertEqual(resp.status_code, 404)

    def test_projects_list_non_searchable(self):
        classroom = self.classroom_obj
        classroom_all_projects = classroom.projects.all()
        self.assertEqual(classroom_all_projects.count(), classroom_all_projects.filter(is_searchable=True).count(), msg='Assumed starting when all projects of classroom are searchable.')

        user = self.classroom_students[0]
        self.client.force_authenticate(user)

        num_classroom_all_projects = classroom_all_projects.count()

        classroom_projects_list_url = reverse('api:classroom-project-list', kwargs={'classroom_pk': classroom.pk})

        resp = self.client.get(classroom_projects_list_url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], num_classroom_all_projects)

        # Hide project in classroom
        project = classroom.projects.all()[0]
        project.is_searchable = False
        project.save()

        # GET /classroom/:id/projects/
        resp = self.client.get(classroom_projects_list_url, {'pageSize': num_classroom_all_projects})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], num_classroom_all_projects)
        self.assertSetEqual(
            set([x['id'] for x in resp.data['results']]),
            set([x.id for x in classroom_all_projects])
        )

    # Tests from PtojectTest that should be skipped.
    def test_get_projects_queries_num(self): pass
    def test_get_projects_with_lessons_queries_num(self): pass
    def test_projects_list_non_searchable_and_purchased(self): pass
