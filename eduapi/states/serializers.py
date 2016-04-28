from django.contrib.auth import get_user_model

from rest_framework import serializers

from api.models import Step, Lesson
from states.models import StepState, LessonState, ProjectState


class StepStateSerializer(serializers.ModelSerializer):
    step        = serializers.PrimaryKeyRelatedField(queryset=Step.objects.all())
    lessonState = serializers.PrimaryKeyRelatedField(source='lesson_state', queryset=LessonState.objects.all())
    user        = serializers.PrimaryKeyRelatedField(queryset=get_user_model().objects.all())

    class Meta:
        model = StepState
        fields = (
            'step',
            'lessonState',
            'user',
        )


class LessonStartSerializer(serializers.ModelSerializer):
    lesson       = serializers.PrimaryKeyRelatedField(queryset=Lesson.objects.all())
    projectState = serializers.PrimaryKeyRelatedField(source='project_state', queryset=ProjectState.objects.all())
    user         = serializers.PrimaryKeyRelatedField(queryset=get_user_model().objects.all())

    class Meta:
        model = LessonState
        fields = (
            'lesson',
            'projectState',
            'user',
        )
