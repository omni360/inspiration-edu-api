from models import BadWord
from django.conf import settings


class BadWordsTool(object):

    @property
    def bad_words_list(self):
        if not hasattr(self, '_bad_words_list'):
            self._bad_words_list = BadWord.get_words_from_cache()
        return self._bad_words_list

    def bad_words_in_sentence(self, sentence):
        # Empty sentence has no bad words:
        if not sentence:
            return []

        # Get bad words from cache
        bad_words_list = self.bad_words_list

        # Return the list of appeared words
        return [bad_word for bad_word in bad_words_list if bad_word in sentence.lower()]
        # import re
        # return list(set(re.compile(r'\b(%s)\b' % '|'.join([re.escape(x) for x in bad_words_list])).findall(sentence.lower())))

    def bad_words_in_text(self, text):
        # Empty text has no bad words:
        if not text:
            return []

        # TODO: find smarter way to split a text and show the sentence
        text_by_sentence = text.splitlines()
        ret = []
        for sentence in text_by_sentence:
            bad_words = self.bad_words_in_sentence(sentence)
            if bad_words:
                ret.append({
                    'sentence': sentence,
                    'bad_words': bad_words
                })
        return ret

    def bad_words_in_instruction(self, instruction, instruction_order, step):
        result = {}

        # Check Instruction description
        bad_words = self.bad_words_in_text(instruction.get('description'))
        if bad_words:
            result['description'] = bad_words

        # Check Instruction hint
        bad_words = self.bad_words_in_text(instruction.get('hint'))
        if bad_words:
            result['hint'] = bad_words

        if len(result) > 0:
            return {'instruction_order': instruction_order, 'issues': result}
        return False

    def bad_words_in_step(self, step):
        result = {}

        # Check Step title
        bad_words = self.bad_words_in_text(step.title)
        if bad_words:
            result['title'] = bad_words

        # Check Step description
        bad_words = self.bad_words_in_text(step.description)
        if bad_words:
            result['description'] = bad_words

        # Check Step instructions
        if step.instructions_list is not None and len(step.instructions_list) > 0:
            instructions_bad_words_result = []
            for instruction_order, instruction in enumerate(step.instructions_list):
                bad_words = self.bad_words_in_instruction(instruction, instruction_order, step)
                if bad_words:
                    instructions_bad_words_result.append(bad_words)
            if instructions_bad_words_result:
                result['instructions'] = instructions_bad_words_result

        if len(result) > 0:
            return {'step_title': step.title, 'step_id': step.id, 'step_order': step.order, 'issues': result}
        return False

    def bad_words_in_lesson(self, lesson):
        result = {}

        # Check Lesson title
        bad_words = self.bad_words_in_text(lesson.title)
        if bad_words:
            result['title'] = bad_words

        # Check video lesson description (stored in application_blob):
        if lesson.application == settings.LESSON_APPS['Video']['db_name'] and lesson.application_blob.get('description'):
            bad_words = self.bad_words_in_text(lesson.application_blob['description'])
            if bad_words:
                result['application_blob_description'] = bad_words

        # Check Lesson steps
        if len(lesson.steps.all()) > 0:
            steps_bad_words_result = []
            for step in lesson.steps.all():
                bad_words = self.bad_words_in_step(step)
                if bad_words:
                    steps_bad_words_result.append(bad_words)
            if len(steps_bad_words_result) > 0:
                result['steps'] = steps_bad_words_result

        if len(result) > 0:
            return {'lesson_title': lesson.title, 'lesson_id': lesson.id, 'issues': result}
        return False

    def bad_words_in_project(self, project):
        result = {}

        # Check project title
        bad_words = self.bad_words_in_text(project.title)
        if bad_words:
            result['title'] = bad_words

        # Check project description
        bad_words = self.bad_words_in_text(project.description)
        if bad_words:
            result['description'] = bad_words

        # Check project teacher info free texts
        bad_words = self.bad_words_in_text(project.teacher_additional_resources)
        if bad_words:
            result['teacher_additional_resources'] = bad_words

        # Check project teacher info free texts
        bad_words = self.bad_words_in_text(project.prerequisites)
        if bad_words:
            result['prerequisites'] = bad_words

        # Check project teacher info free texts
        bad_words = self.bad_words_in_text(project.teacher_tips)
        if bad_words:
            result['teacher_tips'] = bad_words

        # Check project teacher info free texts
        bad_words = self.bad_words_in_text(project.four_cs_creativity)
        if bad_words:
            result['four_cs_creativity'] = bad_words

        # Check project teacher info free texts
        bad_words = self.bad_words_in_text(project.four_cs_critical)
        if bad_words:
            result['four_cs_critical'] = bad_words

        # Check project teacher info free texts
        bad_words = self.bad_words_in_text(project.four_cs_communication)
        if bad_words:
            result['four_cs_communication'] = bad_words

        # Check project teacher info free texts
        bad_words = self.bad_words_in_text(project.four_cs_collaboration)
        if bad_words:
            result['four_cs_collaboration'] = bad_words

        # Check project teacher info free texts
        bad_words = self.bad_words_in_text('\n'.join(project.skills_acquired or ''))
        if bad_words:
            result['skills_acquired'] = bad_words

        # Check project teacher info free texts
        bad_words = self.bad_words_in_text('\n'.join(project.learning_objectives or ''))
        if bad_words:
            result['learning_objectives'] = bad_words

        # Check Lessons
        if len(project.lessons.all()) > 0:
            lessons_bad_words_result = []
            for lesson in project.lessons.all():
                bad_words = self.bad_words_in_lesson(lesson)
                if bad_words:
                    lessons_bad_words_result.append(bad_words)
            if len(lessons_bad_words_result) > 0:
                result['lessons'] = lessons_bad_words_result

        if len(result) > 0:
            return {'project_title': project.title, 'project_id': project.id, 'issues': result}
        return False
