import json
import unittest

from django.db.models import Count, Q
from django.core.urlresolvers import reverse
from django.contrib.auth import get_user_model

from rest_framework.test import APITestCase as DRFTestCase
from edu_api_test_case import EduApiTestCase

from ..serializers import ReviewSerializer
from ..models import Review, IgniteUser, ChildGuardian


class UserReviewsTest(EduApiTestCase, DRFTestCase):
    """
    Tests the ProjectState and LessonState API.
    """

    fixtures = ['test_projects_fixture_1.json']

    def api_test_init(self):
        super(UserReviewsTest, self).api_test_init()

        self.model = Review
        self.serializer = ReviewSerializer

        self.global_user = get_user_model().objects.filter(id=4)

        self.actions = ['list', 'retrieve', 'delete']
        self.sort_key = 'id'
        self.allow_unauthenticated_get = False
        self.allow_subset_of_fields = False
        self.with_choices_on_get = False

        self.api_list_url = reverse('api:user-review-list', kwargs={'user_pk': self.global_user[0].pk})
        self.api_details_url = 'api:user-review-detail'
        self.non_existant_obj_details_url = reverse(self.api_details_url, kwargs={'user_pk': self.global_user[0].pk, 'pk': 44444})
        self.all_user_objects = self.global_user[0].reviews.all()
        self.all_public_objects = self.model.objects.none()

    def get_api_details_url(self, obj, user=None):
        user = user if user is not None else self.global_user
        return reverse(self.api_details_url, kwargs={'user_pk': user.pk, 'pk': obj.pk})


    def test_moderator_can_delete_review(self):
        #add child (that has reviews) to global user (guardian):
        child_with_reviews = IgniteUser.objects.filter(is_child=True).first()
        # child_with_reviews = ChildGuardian.objects.annotate(child_reviews_num=Count('child__reviews')).filter(child_reviews_num__gte=1).first()
        ChildGuardian.objects.get_or_create(guardian=self.global_user, child=child_with_reviews)

        #log the global user (guardian):
        self.client.force_authenticate(self.global_user)

        #make sure moderator can access child reviews:
        resp = self.client.get(reverse('api:user-review-list', kwargs={'user_pk': child_with_reviews.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], child_with_reviews.reviews.count())

        #make sure moderator can delete the child review:
        api_child_review_details = self.get_api_details_url(child_with_reviews.reviews.first(), child_with_reviews)
        resp = self.client.get(api_child_review_details)
        self.assertEqual(resp.status_code, 200)
        resp = self.client.delete(api_child_review_details)
        self.assertIn(resp.status_code, xrange(200, 205))

        #make sure the review is gone:
        resp = self.client.get(api_child_review_details)
        self.assertEqual(resp.status_code, 404)
