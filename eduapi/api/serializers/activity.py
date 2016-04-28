from django.contrib.auth import get_user_model

from rest_framework import serializers

from .reviews import ReviewSerializer
from .projects_classrooms import (
    ProjectStateSerializer,
    ClassroomStateSerializer,
)

class UserActivitySerializer(serializers.ModelSerializer):

    user = serializers.HyperlinkedIdentityField(view_name='api:user-detail')
    reviews = ReviewSerializer(source='activity_reviews', many=True)
    projects = ProjectStateSerializer(source='activity_projects', context={'allowed': ['lessonStates']}, many=True)
    classrooms = ClassroomStateSerializer(source='activity_classrooms', many=True)

    class Meta:
        model = get_user_model()
        fields = (
            'user',
            'reviews',
            'projects',
            'classrooms',
        )
