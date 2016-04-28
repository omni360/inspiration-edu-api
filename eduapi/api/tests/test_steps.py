import json
import copy
import urllib

from django.db.models import F, Count
from django.core.urlresolvers import reverse
from django.contrib.auth import get_user_model
from django.core.serializers.json import DjangoJSONEncoder
from django.conf import settings

from rest_framework.test import APITestCase as DRFTestCase

from edu_api_test_case import EduApiTestCase

from ..serializers import StepSerializer, HtmlField

from ..models import (
    Lesson,
    Step,
    Project,
)

class StepTests(EduApiTestCase, DRFTestCase):
    '''
    Tests the Project API.
    '''

    fixtures = ['test_projects_fixture_1.json']
    model = Step

    def get_api_details_url(self, obj):
        return reverse('api:project-lesson-step-detail', kwargs={
            'project_pk': obj.lesson.project.pk,
            'lesson_pk': obj.lesson.pk,
            'order': obj.order
        })

    def api_test_init(self):
        super(StepTests, self).api_test_init()

        self.global_user = get_user_model().objects.filter(id=2)
        self.lesson = Lesson.objects.annotate(num_steps=Count('steps')).filter(
            project__publish_mode=Project.PUBLISH_MODE_EDIT,
            project__owner_id=2,
            num_steps__gte=1,
        )[0]
        self.lesson_pk = self.lesson.pk
        self.project_pk = self.lesson.project.pk
        self.put_actions = [
            # Successful PUT
            {
                'get_object': lambda: Step.objects.filter(lesson_id=self.lesson_pk).exclude(title='1111111').first(),
                'updated_data': {'title': '1111111'},
            },
            # Can't edit published steps
            # Can't have an empty title
            # Not Authorized
            {
                'user': get_user_model().objects.get(id=4),
                'get_object': lambda: Step.objects.exclude(lesson__project__owner_id=4)[0],
                'expected_result': 403,
            }, 
            # Not Authenticated
            {
                'user': None,
                'get_object': lambda: Step.objects.all()[0],
                'expected_result': 401,
            }
        ]
        self.bulk_actions = ['post', 'put', 'patch', 'delete',]
        self.api_list_url = reverse('api:project-lesson-step-list', kwargs={'project_pk': self.project_pk, 'lesson_pk': self.lesson_pk})
        self.non_existant_obj_details_url = reverse('api:project-lesson-step-detail', kwargs={'project_pk': self.project_pk, 'lesson_pk': self.lesson_pk, 'order': 4444})
        self.all_user_objects = Step.objects.filter(lesson_id=self.lesson_pk).order_by('id')
        self.allow_unauthenticated_get = False
        self.lesson_published = Lesson.objects.annotate(num_steps=Count('steps')).filter(
            project__publish_mode=Project.PUBLISH_MODE_PUBLISHED,
            num_steps__gte=1,
        )[0]  #used for public objects (since unpublished lesson is not accessible to public)
        self.api_list_published_url = reverse('api:project-lesson-step-list', kwargs={'project_pk': self.lesson_published.project.pk, 'lesson_pk': self.lesson_published.pk})
        self.all_public_objects = Step.objects.filter(lesson_id=self.lesson_published.pk).order_by('id')
        self.serializer = StepSerializer
        self.sort_key = 'order'
        self.filters = []
        self.pagination = False

        self.free_text_fields = []

        self.object_to_post = {
            'title': 'First Step',
            'description': 'Learn how to test Django applications using Python\'s unittest',
            'applicationBlob': {},
            'lessonId': self.lesson_pk,
            'order': 4,
            'image': 'http://placekitten.com/250/250/',
        }

        self.field_to_patch = {
            'field': 'title',
            'value': '*NEW TITLE*',
            'exclude': 'description',
        }

    def get_obj_from_api(self, step):
        return self.client.get(self.get_api_details_url(step))

    def patch_obj(self, api_obj, data):
        return self.client.patch(
            api_obj['self'], 
            json.dumps(data, cls=DjangoJSONEncoder),
            content_type='application/json'
        )

    def delete_step_at_position(self, position):

        steps_before = self.all_user_objects.order_by('order')
        steps_ids_before = [s.id for s in steps_before]

        step_to_delete = steps_before[position]

        api_step = self.client.get(self.get_api_details_url(step_to_delete)).data
        self.assertEqual(api_step['order'], position)

        old_parent_updated = step_to_delete.lesson.updated

        resp = self.client.delete(api_step['self'])

        self.assertEqual(resp.status_code, 204)

        steps_ids_after = [
            s.id 
            for s 
            in self.all_user_objects.order_by('order')
        ]

        del steps_ids_before[position]
        self.assertListEqual(list(steps_ids_before), list(steps_ids_after))

        # check that parent 'updated' was changed:
        parent = Lesson.objects.get(id=step_to_delete.lesson.id)
        self.assertGreater(parent.updated, old_parent_updated)
        self.assertEqual(parent.project.updated, parent.updated)

    def add_step_at_position(self, position):

        num_of_steps = self.all_user_objects.count()
        if position > num_of_steps:
            should_be_idx = num_of_steps
        else:
            should_be_idx = position


        steps_before = self.all_user_objects.order_by('order')
        steps_ids_before = [s.id for s in steps_before]

        step_to_add = self.object_to_post
        step_to_add['order'] = position

        resp = self.client.post(self.api_list_url, json.dumps(
            step_to_add,
            cls=DjangoJSONEncoder,
        ), content_type='application/json')

        self.assertIn(resp.status_code, xrange(200, 205))

        self.assertEqual(resp.data['order'], should_be_idx)

        steps_ids_after = [
            s.id 
            for s 
            in self.all_user_objects.order_by('order')
        ]

        steps_ids_before.insert(should_be_idx, resp.data['id'])
        self.assertListEqual(list(steps_ids_before), list(steps_ids_after))

        # check that parent 'updated' was changed:
        step_obj = Step.objects.get(id=resp.data['id'])
        self.assertEqual(step_obj.lesson.updated, step_obj.updated)
        self.assertEqual(step_obj.lesson.project.updated, step_obj.updated)

    # Tests
    # #####

    def test_steps_limit_is_at_least_50(self):

        from ..models import Project
        lesson_obj_to_post = {
            'title': 'Testing 101',
            'publishMode': Project.PUBLISH_MODE_PUBLISHED,
            'description': 'Learn how to test Django applications using Python\'s unittest',
            'duration': 45,
            'image': 'http://placekitten.com/300/300/',
            'difficulty': Project.DIFFICULTIES[0][0],
            'license': Project.LICENSES[0][0],
            'age': Project.AGES[0][0],
            'application': settings.LESSON_APPS['Video']['db_name'],
            'applicationBlob': {
                'video': {
                    'vendor': 'youtube',
                    'id': '1234567890a',
                },
            },
            'order': 0,
        }

        resp = self.client.post(reverse('api:project-lesson-list', kwargs={'project_pk': self.project_pk}), json.dumps(
            lesson_obj_to_post,
            cls=DjangoJSONEncoder
        ), content_type='application/json')

        self.assertIn(resp.status_code, xrange(200,204))
        self.assertIn('id', resp.data)
        lesson = resp.data

        for idx in xrange(0,50):

            resp = self.client.post(
                reverse('api:project-lesson-step-list', kwargs={'project_pk': lesson['projectId'], 'lesson_pk': lesson['id']}),
                json.dumps(
                    self.object_to_post,
                    cls=DjangoJSONEncoder
                ),
                content_type='application/json',
            )

            self.assertIn(resp.status_code, xrange(200,204))

        self.assertEqual(Step.objects.filter(lesson_id=lesson['id']).count(), 50)

        resp = self.client.get(reverse('api:project-lesson-step-list', kwargs={'project_pk': lesson['projectId'], 'lesson_pk': lesson['id']}))

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['results']), 50)

    def test_cant_post_if_not_authenticated(self):

        self.client.force_authenticate(None)

        resp = self.client.post(self.api_list_url, json.dumps(
            self.object_to_post,
            cls=DjangoJSONEncoder
        ), content_type='application/json')

        self.assertIn(resp.status_code, [401])

    def test_cant_post_to_not_owned_lesson(self):

        # Log in with a user that doesn't own the lesson
        self.client.force_authenticate(
            get_user_model().objects.filter(
                is_superuser=False,
            ).exclude(
                id=self.global_user.id
            ).exclude(
                id__in=self.global_user.delegates.all()
            ).exclude(
                id__in=self.global_user.guardians.all()
            )[0]
        )

        resp = self.client.post(self.api_list_url, json.dumps(
            self.object_to_post,
            cls=DjangoJSONEncoder
        ), content_type='application/json')

        self.assertIn(resp.status_code, [403, 404])


    def test_get_instructions(self):
        
        step = self.all_user_objects.filter(instructions_list__len__gte=3).first()

        api_step = self.get_obj_from_api(step).data
        self.assertGreaterEqual(len(api_step['instructions']), 3)

        db_instructions = step.instructions_list
        self.assertEqual(len(db_instructions), len(api_step['instructions']))

        # Make sure that each instruction in the step, is true to the DB.
        for idx, db_instr in enumerate(db_instructions):
            self.assertEqual(db_instr, api_step['instructions'][idx])

    def test_add_instructions_to_empty_list(self):
        step = self.all_user_objects.filter(instructions_list__isnull=True)[0]

        api_step = self.get_obj_from_api(step).data
        self.assertFalse(api_step['instructions'])

        resp = self.patch_obj(api_step, {
            'instructions': [{
                'description': 'instruction %s' % i,
                'image': 'http://host.com/myimage_%s.jpg' %i,
            } for i in xrange(5)]
        })

        self.assertIn(resp.status_code, range(200,205))

        db_instructions_list = Step.objects.get(
            id=step.id
        ).instructions_list
        self.assertListEqual(db_instructions_list, list(resp.data['instructions']))

    def test_modify_instructions_list(self):
        
        step = self.all_user_objects.filter(instructions_list__len__gte=3).first()

        api_step = self.get_obj_from_api(step).data
        api_instructions = api_step['instructions']
        self.assertGreaterEqual(len(api_instructions), 3)

        resp = self.patch_obj(api_step, {
            'instructions': api_instructions[1:2] + 
            [{
                'description': 'instruction %s' % i,
                'image': 'http://host.com/myimage_%s.jpg' %i,
            } for i in xrange(3)] +
            api_instructions[2:]
        })

        self.assertIn(resp.status_code, range(200,205))

        db_instructions_list = Step.objects.get(
            id=step.id
        ).instructions_list
        self.assertListEqual(db_instructions_list, list(resp.data['instructions']))

        self.assertNotIn(api_step['instructions'][0], db_instructions_list)

    def test_add_instructions_to_existing_list(self):
        
        step = self.all_user_objects.filter(instructions_list__len__gte=1).first()

        api_step = self.get_obj_from_api(step).data
        self.assertGreaterEqual(len(api_step['instructions']), 3)

        instructions = api_step['instructions'] + [{'description': u'one more instruction with special \u2126 character'}]
        resp = self.patch_obj(api_step, {
            'instructions': instructions
        })

        self.assertIn(resp.status_code, range(200,205))

        db_instructions_list = Step.objects.get(
            id=step.id
        ).instructions_list
        self.assertListEqual(db_instructions_list, list(resp.data['instructions']))
        self.assertEqual(instructions[-1]['description'], resp.data['instructions'][-1]['description'])

    def test_patch_step_do_not_send_instructions_to_existing_list(self):

        step = self.all_user_objects.filter(instructions_list__len__gte=3).first()

        api_step = self.get_obj_from_api(step).data
        self.assertGreaterEqual(len(api_step['instructions']), 3)

        resp = self.patch_obj(api_step, {
            'title': 'new title'
        })

        self.assertIn(resp.status_code, range(200,205))

        db_instructions = Step.objects.get(
            id=step.id
        ).instructions_list

        self.assertListEqual(db_instructions, step.instructions_list)

        resp = self.patch_obj(api_step, {
            'title': 'new title'
        })

        self.assertIn(resp.status_code, range(200,205))

        db_instructions = Step.objects.get(
            id=step.id
        ).instructions_list

        self.assertListEqual(db_instructions, step.instructions_list)

    def test_remove_instructions_from_existing_list(self):
        step = self.all_user_objects.filter(instructions_list__len__gte=3).first()

        api_step = self.get_obj_from_api(step).data
        self.assertGreaterEqual(len(api_step['instructions']), 3)

        resp = self.patch_obj(api_step, {
            'instructions': api_step['instructions'][0:1] + api_step['instructions'][2:]
        })

        self.assertIn(resp.status_code, range(200,205))

        db_instructions_list = Step.objects.get(
            id=step.id
        ).instructions_list
        self.assertListEqual(db_instructions_list, list(resp.data['instructions']))
        self.assertNotIn(api_step['instructions'][1], db_instructions_list)


    def test_remove_all_instructions(self):

        step = self.all_user_objects.filter(instructions_list__len__gte=3).first()

        api_step = self.get_obj_from_api(step).data
        self.assertGreaterEqual(len(api_step['instructions']), 3)

        temp_instructions = api_step['instructions']

        resp = self.patch_obj(api_step, {'instructions': []})

        self.assertIn(resp.status_code, range(200,205))

        self.assertEqual(len(Step.objects.get(id=step.id).instructions_list), 0)

        self.assertEqual(len(resp.data['instructions']), 0)

        self.patch_obj(api_step, {'instructions': list(temp_instructions)})

    def test_delete_step_then_add_step_with_same_order(self):
        '''
        This test follows a bug. The steps (haha) required to reproduce the bug
        are: 
        1. Create a step with order (e.g.) 0 for the lesson.
        2. Delete the step.
        3. Create a new lesson with the same order (0) for the lesosn.
        4. Got an Integrity error beacause the first step wasn't deleted (only
           marked deleted).
        '''

        # Make sure that object_to_post contains "order".
        self.assertIn('order', self.object_to_post)
        
        # POST step
        resp = self.client.post(self.api_list_url, json.dumps(
            self.object_to_post,
            cls=DjangoJSONEncoder
        ), content_type='application/json')

        self.assertIn(resp.status_code, xrange(200,205))

        step_to_delete = resp.data

        # DELETE posted step
        resp2 = self.client.delete(reverse('api:project-lesson-step-detail', kwargs={
            'project_pk': self.project_pk,
            'lesson_pk': self.lesson_pk,
            'order': step_to_delete['order']
        }))

        self.assertEqual(resp2.status_code, 204)

        # POST step again with same order field.
        resp3 = self.client.post(self.api_list_url, json.dumps(
            self.object_to_post,
            cls=DjangoJSONEncoder
        ), content_type='application/json')

        # Make sure POST succeeeds.
        self.assertIn(resp3.status_code, xrange(200,205))

        # GET all of the steps
        all_steps = self.client.get(reverse('api:lesson-detail', kwargs={
            'pk': self.lesson_pk
        }), {'embed': 'steps'}).data['steps']
        all_steps_ids = [s['id'] for s in all_steps]

        # Make sure that new step is in lesson and deleted step isn't.
        self.assertIn(resp3.data['id'], all_steps_ids)
        self.assertNotIn(resp.data['id'], all_steps_ids)

    def test_putting_step_doesnt_change_order(self):

        step = self.all_user_objects[0]

        api_step = self.client.get(self.get_api_details_url(step)).data

        steps_order_before = [
            s.order
            for s 
            in Step.objects.filter(
                lesson_id=api_step['lessonId'],
            ).order_by('order')
        ]

        resp = self.client.put(api_step['self'], json.dumps(
            api_step,
            cls=DjangoJSONEncoder
        ), content_type='application/json')

        self.assertIn(resp.status_code, xrange(200, 205))

        steps_order_after = [
            s.order
            for s 
            in Step.objects.filter(
                lesson_id=api_step['lessonId'],
            ).order_by('order')
        ]

        self.assertListEqual(steps_order_before, steps_order_after)

    def test_moving_a_step_around(self):

        num_of_steps = len(self.all_user_objects)
        self.assertGreaterEqual(num_of_steps, 7)

        moves = (
            (2, 5),
            (5, 3),
            (4, 0),
            (5, num_of_steps - 1),
            (0, num_of_steps - 1),
            (4, num_of_steps + 5),
            (0, 3),
            (num_of_steps - 1, 0),
            (num_of_steps - 1, 4),
        )

        for from_idx, to_idx in moves:

            if to_idx > num_of_steps:
                should_be_idx = num_of_steps - 1
            else:
                should_be_idx = to_idx

            steps_before = self.all_user_objects.order_by('order')
            steps_ids_before = [s.id for s in steps_before]

            step_to_move = steps_before[from_idx]

            api_step_to_move = self.client.get(self.get_api_details_url(step_to_move)).data
            self.assertEqual(api_step_to_move['order'], from_idx)

            api_step_to_move['order'] = to_idx

            resp = self.client.put(api_step_to_move['self'], json.dumps(
                api_step_to_move,
                cls=DjangoJSONEncoder
            ), content_type='application/json')

            self.assertIn(resp.status_code, xrange(200, 205))
            self.assertEqual(resp.data['order'], should_be_idx)

            steps_ids_after = [s.id for s in Step.objects.filter(
                lesson_id=api_step_to_move['lessonId']
            ).order_by('order')]
            del steps_ids_before[from_idx]
            steps_ids_before.insert(should_be_idx, api_step_to_move['id'])
            self.assertListEqual(list(steps_ids_before), list(steps_ids_after))

    def test_delete_first_step(self):
        self.delete_step_at_position(0)

    def test_delete_last_step(self):
        self.delete_step_at_position(self.all_user_objects.count() - 1)

    def test_delete_middle_step(self):
        self.delete_step_at_position(int(self.all_user_objects.count() / 2))

    def test_add_to_beginning_of_steps(self):
        self.add_step_at_position(0)

    def test_add_to_end_of_steps(self):
        self.add_step_at_position(self.all_user_objects.count())

    def test_add_to_middle_of_steps(self):
        self.add_step_at_position(int(self.all_user_objects.count() / 2))

    def test_save_step_for_new_lesson(self):

        lesson = Lesson.objects.all().annotate(
            steps_num=Count('steps')
        ).filter(
            steps_num=0,
            project__publish_mode=Project.PUBLISH_MODE_EDIT,
            project__owner=self.global_user,
        )[0]

        step_to_add = self.object_to_post
        step_to_add['order'] = 4

        resp = self.client.post(reverse('api:project-lesson-step-list', kwargs={
            'project_pk': lesson.project_id,
            'lesson_pk': lesson.id
        }), json.dumps(
            step_to_add,
            cls=DjangoJSONEncoder,
        ), content_type='application/json')

        self.assertIn(resp.status_code, xrange(200, 205))

        self.assertEqual(resp.data['order'], 0)

        steps_ids_after = [
            s.id 
            for s 
            in Step.objects.filter(lesson_id=lesson.id).order_by('order')
        ]

        self.assertListEqual([resp.data['id']], list(steps_ids_after))


    def test_get_list_of_published_lesson(self):
        self.client.force_authenticate(self.global_user)
        self.test_get_list(self.api_list_published_url, self.all_public_objects)

    def test_get_object_of_published_lesson(self):
        self.client.force_authenticate(self.global_user)
        self.test_get_object(self.all_public_objects)

    def test_serializer_html_field_sanitization(self):
        '''
        Tests that serializer HtmlField sanitizes HTML properly.
        '''
        test_htmls = [
            ('<h1>Title</h1>\n<p><b>HELLO</b> There... <script>alert("HA HA");</script></p>',
             '<h1>Title</h1>\n<p><b>HELLO</b> There... alert("HA HA");</p>'),  #remove <script>
            ('<p>See this:<br><img alt="NOT ALLOWED!" height="100" src="http://pic.com/image.jpg" width="100"></p>',
             '<p>See this:<br></p>'),  #remove <img>
            ('<a href="http://go.com/there/" onclick="alert(\\"HA HA\\");">Allow Link</a>',
             '<a href="http://go.com/there/">Allow Link</a>'),  #remove not allowed attributes
            ('<p>Line 1<br />\nLine 2</p>',
             '<p>Line 1<br>\nLine 2</p>'),  #XHTML tags to HTML
            ('<p dir="rtl">This line is <span="rtl">RTL</span>!</p>',
             '<p dir="rtl">This line is RTL!</p>',),  #allow dir attribute
        ]

        html_field = HtmlField()
        for test_html in test_htmls:
            ret_val = html_field.to_internal_value(test_html[0])
            self.assertEqual(ret_val, test_html[1])

    def test_step_description_field_html_sanitization(self):
        '''
        Tests that Step's description HtmlField sanitizes HTML properly.
        '''
        test_htmls = [
            ('<h1>Title</h1>\n<p><b>HELLO</b> There... <script>alert("HA HA");</script></p>',
             '<h1>Title</h1>\n<p><b>HELLO</b> There... alert("HA HA");</p>'),  #remove <script>
            ('<p>See this:<br><img alt="ALLOWED!" height="100" src="http://pic.com/image.jpg" width="100"></p>',
             '<p>See this:<br><img alt="ALLOWED!" height="100" src="http://pic.com/image.jpg" width="100"></p>'),  #allow <img>
            ('<a href="http://go.com/there/" onclick="alert(\\"HA HA\\");">Allow Link</a>',
             '<a href="http://go.com/there/">Allow Link</a>'),  #remove not allowed attributes
            ('<p>Line 1<br />\nLine 2</p>',
             '<p>Line 1<br>\nLine 2</p>'),  #XHTML tags to HTML
            ('<p dir="rtl">This line is <span="rtl">RTL</span>!</p>',
             '<p dir="rtl">This line is RTL!</p>',),  #allow dir attribute
        ]

        html_field = StepSerializer().fields['description']
        for test_html in test_htmls:
            ret_val = html_field.to_internal_value(test_html[0])
            self.assertEqual(ret_val, test_html[1])

    def test_post_steps_changes_lesson_and_project_updated_field(self):
        kwargs_list = []
        for i in xrange(0,3):
            kwargs = copy.deepcopy(self.object_to_post)
            if not kwargs:
                return
            kwargs_list.append(kwargs)

        resp = self.client.post(self.api_list_url, json.dumps(
            kwargs_list,
            cls=DjangoJSONEncoder
        ), content_type='application/json')
        self.assertIn(resp.status_code, [200, 201, 202, 203])
        self.assertEqual(len(resp.data), len(kwargs_list))

        # check that parent 'updated' was changed:
        last_updated_obj = Step.objects.get(id=resp.data[-1]['id'])
        self.assertEqual(last_updated_obj.lesson.updated, last_updated_obj.updated)
        self.assertEqual(last_updated_obj.lesson.project.updated, last_updated_obj.updated)

    def test_delete_steps_changes_lesson_and_project_updated_field(self):
        object_to_delete = self.object_to_delete if self.object_to_delete is not None else self.all_user_objects[0]

        old_parent_updated = object_to_delete.lesson.updated

        resp = self.client.delete(
            self.api_list_url + '?' + urllib.urlencode({self.lookup_field+'List': ','.join([str(object_to_delete.id), '-1', 'invalid'])}),
        )
        self.assertEqual(resp.status_code, 204)

        # check that parent 'updated' was changed:
        parent = Lesson.objects.get(id=object_to_delete.lesson.id)
        self.assertGreater(parent.updated, old_parent_updated)
        self.assertEqual(parent.project.updated, parent.updated)

    def test_patch_steps_changes_lesson_and_project_updated_field(self):
        objects_to_patch = self.all_user_objects[:3]
        data_list, data_modified_list = [], []
        for object_to_patch in objects_to_patch:
            data = self.client.get(self.get_api_details_url(object_to_patch)).data
            data_list.append(data)

            data_modified = copy.deepcopy(data)
            data_modified[self.field_to_patch['field']] = self.field_to_patch['value']
            del data_modified[self.field_to_patch['exclude']]
            data_modified_list.append(data_modified)

        resp = self.client.patch(self.api_list_url,
                                 json.dumps(data_modified_list, cls=DjangoJSONEncoder),
                                 content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # check that parent 'updated' was changed:
        last_updated_obj = Step.objects.get(id=resp.data[-1]['id'])
        self.assertEqual(last_updated_obj.lesson.updated, last_updated_obj.updated)
        self.assertEqual(last_updated_obj.lesson.project.updated, last_updated_obj.updated)
