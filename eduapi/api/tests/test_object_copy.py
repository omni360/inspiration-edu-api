from django.contrib.auth import get_user_model
from django.core.serializers.json import DjangoJSONEncoder
from django.core.urlresolvers import reverse
from django.db.models import Count, Q
from django.test import TestCase
from rest_framework.test import APITestCase
from api.models import Step, Lesson, Project
import json

class NotificationsTests(TestCase):
    fixtures = ['test_projects_fixture_1.json']

    def setUp(self):
        self.step_with_several_instructions = Step.objects.filter(instructions_list__len__gt=5).first()
        self.lesson_with_several_steps = Lesson.objects.annotate(
            num_of_steps=Count('steps')
        ).filter(num_of_steps__gt=1)[0]

    def test_copy_steps(self):
        to_lesson = Lesson.objects.create(
            title='Test lesson title',
            application='123dcircuits',
            project=Project.objects.all()[0]
        )
        self.lesson_with_several_steps.copy_lesson_steps(
            to_lesson=to_lesson
        )
        # Check that new lesson have the same number of steps
        self.assertEquals(
            self.lesson_with_several_steps.num_of_steps,
            Lesson.objects.get(id=to_lesson.id).steps.all().count()
        )
        # And this number is not 0
        self.assertFalse(
            0 == Lesson.objects.get(id=to_lesson.id).steps.all().count()
        )
        # Check that order is saved
        for step in Lesson.objects.get(id=to_lesson.id).steps.all():
            self.assertEquals(
                self.lesson_with_several_steps.steps.all()[step.order].title,
                step.title
            )

    def test_copy_lesson(self):
        to_project = Project.objects.create(
            title='Test lesson title',
            owner=get_user_model().objects.all()[0]
        )
        self.lesson_with_several_steps.copy_lesson_to_project(
            to_project=to_project
        )
        # Check that new lesson have the same number of steps
        self.assertEquals(
            to_project.lessons.all()[0].steps.all().count(),
            self.lesson_with_several_steps.steps.all().count()
        )
        self.assertEquals(
            self.lesson_with_several_steps.steps_count,
            to_project.lessons.all()[0].steps_count,
        )
        # And this number is not 0
        self.assertFalse(
            0 == to_project.lessons.all()[0].steps.all().count()
        )
        # Check that order is saved
        for step in to_project.lessons.all()[0].steps.all():
            old_step = self.lesson_with_several_steps.steps.all()[step.order]
            self.assertEquals(
                old_step.title,
                step.title
            )
            # Do the same for instructions
            if old_step.instructions_list == None:
                self.assertEqual(step.instructions_list, None)
            else:
                self.assertListEqual(old_step.instructions_list, step.instructions_list)


class ObjectCopyApiTests(APITestCase):
    """
    Tests the ProjectState and LessonState API.
    """

    fixtures = ['test_projects_fixture_1.json']

    def test_copy_by_permitted_user_to_be_successful(self):
        # get user owning 2 projects and authenticate
        user = get_user_model().objects.annotate(projects_count=Count('authored_projects')).filter(projects_count__gt=1)[0]
        self.client.force_authenticate(user)

        # copy lesson from one project to another
        projects = user.authored_projects.all()
        lesson_from_project_1 = projects.filter(lessons__isnull=False)[0].lessons.all()[0]
        project_2 = projects.filter(publish_mode=Project.PUBLISH_MODE_EDIT).exclude(id=lesson_from_project_1.project_id)[0]

        # Send the request
        url_to_copy = reverse('api:project-lesson-list', kwargs={'project_pk': project_2.id })
        url_to_copy += '?copyFromLessonsIds=%s' % lesson_from_project_1.id
        resp = self.client.post(
            url_to_copy,
            json.dumps({}),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 201)

    def test_copy_multiple_lessons_by_permitted_user_should_return_list(self):
        # get user owning 3 projects and authenticate
        user = get_user_model().objects.annotate(projects_count=Count('authored_projects')).filter(projects_count__gt=2)[0]
        self.client.force_authenticate(user)

        # copy lesson from one project to another
        projects = user.authored_projects.all()
        lesson_from_project_1 = projects.filter(lessons__isnull=False)[0].lessons.all()[0]
        lesson_from_project_2 = projects.filter(lessons__isnull=False)[1].lessons.all()[0]
        lessons = [lesson_from_project_1, lesson_from_project_2]
        project_3 = projects.filter(publish_mode=Project.PUBLISH_MODE_EDIT).exclude(id__in=[x.project_id for x in lessons])[0]

        # Send the request
        url_to_copy = reverse('api:project-lesson-list', kwargs={'project_pk': project_3.id })
        url_to_copy += '?copyFromLessonsIds=%s' % ', '.join([str(x.id) for x in lessons])
        url_to_copy += '&embed=stepsIds'
        resp = self.client.post(
            url_to_copy,
            json.dumps({}),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 201)

        for idx, l in enumerate(lessons):
            self.assertEqual(resp.data[idx]['title'], l.title)
            self.assertEqual(resp.data[idx]['projectId'], project_3.id)
            self.assertEqual(len(resp.data[idx]['stepsIds']), l.steps.count())

    def test_copy_owned_lesson_to_not_owned_project_should_fail(self):
        # get user owning 2 projects and authenticate
        user = get_user_model().objects.annotate(projects_count=Count('authored_projects')).filter(projects_count__gt=1)[0]
        self.client.force_authenticate(user)

        # Find owned lesson
        lesson_to_copy = user.authored_projects.all().filter(lessons__isnull=False)[0].lessons.all()[0]
        # Find not owned project
        project_2 = Project.objects.exclude(
            Q(owner=user) |
            Q(owner__in=user.children.all()) |
            Q(owner__in=user.delegators.all())
        )[0]
        # and make sure it is not published
        project_2.publish_mode = Project.PUBLISH_MODE_EDIT
        project_2.save()

        # Send the request
        url_to_copy = reverse('api:project-lesson-list', kwargs={'project_pk': project_2.id })
        resp = self.client.get(url_to_copy)
        self.assertEqual(resp.status_code, 404)
        url_to_copy += '?copyFromLessonsIds=%s' % lesson_to_copy.id
        resp = self.client.post(
            url_to_copy,
            json.dumps({}),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 404)

    def test_copy_owned_lesson_to_edit_locked_project_should_fail(self):
        # get user owning 2 projects and authenticate
        user = get_user_model().objects.annotate(projects_count=Count('authored_projects')).filter(projects_count__gt=1)[0]
        self.client.force_authenticate(user)

        # copy lesson from one project to another
        projects = user.authored_projects.all()
        lesson_from_project_1 = projects.filter(lessons__isnull=False)[0].lessons.all()[0]
        project_2 = projects.filter(publish_mode=Project.PUBLISH_MODE_EDIT).exclude(id=lesson_from_project_1.project_id)[0]

        # lock project to copy to:
        project_2.current_editor = get_user_model().objects.exclude(id=user.id).first()
        project_2.save()

        # Send the request
        url_to_copy = reverse('api:project-lesson-list', kwargs={'project_pk': project_2.id })
        url_to_copy += '?copyFromLessonsIds=%s' % lesson_from_project_1.id
        resp = self.client.post(
            url_to_copy,
            json.dumps({}),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 403)

    def test_copy_by_user_not_owning_lesson_should_fail(self):
        # get user owning 2 projects and authenticate
        user = get_user_model().objects.annotate(projects_count=Count('authored_projects')).filter(projects_count__gt=1)[0]
        self.client.force_authenticate(user)

        # copy lesson from one project to another
        lesson_to_copy = Project.objects.filter(publish_mode=Project.PUBLISH_MODE_PUBLISHED, lessons__isnull=False).exclude(owner=user)[0].lessons.all()[0]
        project_2 = user.authored_projects.all().filter(publish_mode=Project.PUBLISH_MODE_EDIT).exclude(id=lesson_to_copy.project_id)[0]

        # Send the request
        url_to_copy = reverse('api:project-lesson-list', kwargs={'project_pk': project_2.id })
        url_to_copy += '?copyFromLessonsIds=%s' % lesson_to_copy.id
        resp = self.client.post(
            url_to_copy,
            json.dumps({}),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 400)

    def test_copy_multiple_lessons_with_lessons_init_settings(self):
        # get user owning 3 projects and authenticate
        user = get_user_model().objects.annotate(projects_count=Count('authored_projects')).filter(projects_count__gt=2)[0]
        self.client.force_authenticate(user)

        # schema of lessons init groups:
        projects_lessons_init_nums = [[2, 2,], [1, 1, 2]]
        num_lessons_to_copy = 3

        # copy lesson from one project to another
        projects = user.authored_projects.all()
        src_projects = projects.annotate(num_lessons=Count('lessons')).filter(num_lessons__gt=3)[:2]
        lessons_to_copy = []
        for src_project in src_projects:
            project_lessons = list(src_project.lessons.all())
            lessons_to_copy += project_lessons[-num_lessons_to_copy:]
            lessons_init = []
            lessons_init_nums = projects_lessons_init_nums.pop()
            for lessons_init_num in lessons_init_nums:
                lessons_ids = []
                for i in range(lessons_init_num):
                    lessons_ids.append(project_lessons.pop().id)
                lessons_init.append({
                    'lessonsIds': lessons_ids,
                    'initCanvasId': 'canvas-A',
                })
            src_project.extra = {'lessonsInit': lessons_init}
            src_project.save()
        lessons_to_copy_ids = [x.id for x in lessons_to_copy]
        dest_project = projects.filter(publish_mode=Project.PUBLISH_MODE_EDIT).exclude(id__in=[x.project_id for x in lessons_to_copy])[0]
        dest_project.extra = None
        dest_project.save()

        # Send the request
        url_to_copy = reverse('api:project-lesson-list', kwargs={'project_pk': dest_project.id })
        url_to_copy += '?copyFromLessonsIds=%s' % ', '.join([str(x.id) for x in lessons_to_copy])
        url_to_copy += '&embed=stepsIds'
        resp = self.client.post(
            url_to_copy,
            json.dumps({}),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 201)

        lessons_copied_dict = {}
        for idx, l in enumerate(lessons_to_copy):
            self.assertEqual(resp.data[idx]['title'], l.title)
            self.assertEqual(resp.data[idx]['projectId'], dest_project.id)
            self.assertEqual(len(resp.data[idx]['stepsIds']), l.steps.count())
            lessons_copied_dict[resp.data[idx]['id']] = l.id

        # Check that destination project contains the lessons init copied from source lessons projects:
        dest_project = Project.objects.get(pk=dest_project.pk)
        for lessons_group in dest_project.extra['lessonsInit']:
            lessons_ids_src = [lessons_copied_dict[x] for x in lessons_group['lessonsIds']]
            lesson_id_src = lessons_ids_src[0]
            lessons_group_match = None
            for src_project in src_projects:
                for lessons_group_src in src_project.extra['lessonsInit']:
                    if lesson_id_src in lessons_group_src['lessonsIds']:
                        lessons_group_match = lessons_group_src
                        break
                if lessons_group_match:
                    break
            if not lessons_group_match:
                self.fail(msg='Lesson init in destination project is not found in any source project.')
            expected_lessons_ids_src = [x for x in lessons_group_match['lessonsIds'] if x in lessons_to_copy_ids]
            self.assertEqual(lessons_ids_src, expected_lessons_ids_src)
