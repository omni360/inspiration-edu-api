from django.core import cache as django_cache
from mock import patch

from rest_framework.test import APITestCase
from api.models import Project, Lesson, Step
from editor_tools import models as bad_word_models
from editor_tools.tools import BadWordsTool
BadWord = bad_word_models.BadWord


class EditorToolsTests(APITestCase):
    fixtures = ['test_projects_fixture_1.json']

    @classmethod
    def setUpTestData(cls):
        cls.text = 'Lorem Ipsum is simply dummy text of the printing and' \
                   ' typesetting industry. Lorem Ipsum has been the industry' \
                   ' standard dummy text ever since the 1500s, when an unknown' \
                   ' printer took a galley of type and scrambled it to make a' \
                   ' type specimen book. It has survived not only five centuries,' \
                   ' but also the leap into electronic typesetting, remaining' \
                   ' essentially unchanged. It was popularised in the 1960s' \
                   ' with the release of Letraset sheets containing Lorem Ipsum' \
                   ' passages, and more recently with desktop publishing software' \
                   ' like Aldus PageMaker including versions of Lorem Ipsum.'
        cls.bad_word = 'text'

    def setUp(self):
        self.locmem_cache = django_cache.get_cache('django.core.cache.backends.locmem.LocMemCache')
        self.locmem_cache.clear()
        self.patch = patch.object(bad_word_models, 'cache', self.locmem_cache)
        self.patch.start()

        # initialize bad words:
        BadWord.objects.create(text=self.bad_word)
        self.bad_words_tool = BadWordsTool()

    def tearDown(self):
        self.patch.stop()

    def test_bad_word_found_in_a_string_and_returned(self):
        bad_words = self.bad_words_tool.bad_words_in_sentence('Lorem Ipsum is simply dummy text of the printing and typesetting industry.')
        self.assertTrue(self.bad_word in bad_words)

    def test_bad_words_added_to_cache(self):
        BadWord.objects.create(text='bad_word')
        self.assertIsNotNone(self.locmem_cache.get('bad_words_list', None))

    def test_bad_word_found_in_a_text_and_returned(self):
        results = self.bad_words_tool.bad_words_in_text(self.text)
        self.assertGreater(len(results), 0)

        for row in results:
            self.assertTrue(row.get('bad_words')[0] in row.get('sentence'))

    def test_bad_words_in_a_project(self):
        BadWord.objects.create(text='Star')
        project = Project.objects.filter(title__icontains='star')[0]
        bad_words = self.bad_words_tool.bad_words_in_project(project)

        self.assertIsNotNone(bad_words.get('issues'))

    def test_bad_words_in_a_lesson(self):
        BadWord.objects.create(text='Lesson')
        project = Project.objects.get(pk=22)
        bad_words = self.bad_words_tool.bad_words_in_project(project)

        self.assertIsNotNone(bad_words.get('issues').get('lessons'))

    def test_bad_words_in_a_step(self):
        BadWord.objects.create(text='Python')
        lesson = Lesson.objects.get(pk=1)

        bad_words = self.bad_words_tool.bad_words_in_lesson(lesson)

        self.assertIsNotNone(bad_words.get('issues'))

    def test_bad_words_in_a_instructions(self):
        BadWord.objects.create(text='One')
        step = Step.objects.get(pk=1)

        bad_words = self.bad_words_tool.bad_words_in_step(step)

        self.assertIsNotNone(bad_words.get('issues'))