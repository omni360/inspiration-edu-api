import unittest

from django.db.models import Q, Count
from django.core.urlresolvers import reverse
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from rest_framework.test import APITestCase as DRFTestCase

from edu_api_test_case import EduApiTestCase
from common_review_tests import CommonReviewTests

from ..serializers import ReviewSerializer
from ..models import (
    Review,
    Project,
)


class ProjectReviewTests(EduApiTestCase, CommonReviewTests, DRFTestCase):
    '''
    Tests the Project API.
    '''

    fixtures = ['test_projects_fixture_1.json']

    def api_test_init(self):
        super(ProjectReviewTests, self).api_test_init()

        self.project = Project.objects.annotate(num_reviews=Count('reviews')).filter(publish_mode=Project.PUBLISH_MODE_PUBLISHED, num_reviews__gt=0)[0]
        self.all_public_objects = self.project.reviews.all()
        self.global_user = get_user_model().objects.filter(id=self.all_public_objects[0].owner.id)
        self.all_user_objects = self.all_public_objects
        self.all_user_objects_for_edit = self.all_user_objects.filter(owner=self.global_user)

        self.api_list_url = reverse('api:project-review-list', kwargs={'project_pk': self.project.id})
        self.api_details_url = reverse('api:project-review-detail', kwargs={'project_pk': 1, 'pk': self.all_user_objects[0].pk})
        self.non_existant_obj_details_url = reverse('api:project-review-detail', kwargs={'project_pk': self.project.id, 'pk': 4444})

        self.serializer = ReviewSerializer
        self.sort_key = 'id'
        self.pagination = False

        self.content_type = 'project'

        self.free_text_fields = ['text', ]

        self.object_to_post = {
            'text': 'This is a test review',
            'rating': 8
        }

        self.object_to_delete = self.all_user_objects_for_edit[0]

    def setUp(self):

        super(ProjectReviewTests, self).setUp()

        self.all_public_objects = Review.objects.filter(
            Q(content_type=ContentType.objects.get_for_model(Project))
        )
        self.all_user_objects = Review.objects.filter(
            Q(owner=self.global_user) &
            Q(content_type=ContentType.objects.get_for_model(Project))
        )

    @unittest.skip('Not implemented')
    def test_get_list_subset_of_fields(self):
        pass

    def get_api_details_url(self, obj):

        return reverse('api:project-review-detail', kwargs={
            'pk': obj.id,
            'project_pk': obj.object_id,
        })

    def test_get_list(self, api_list_url=None, db_objs=None):
        super(ProjectReviewTests, self).test_get_list(db_objs=self.project.reviews.all())
