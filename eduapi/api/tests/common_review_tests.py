import re
import json
import copy

from django.db.models import Q
from django.contrib.auth import get_user_model
from django.core.serializers.json import DjangoJSONEncoder
from django.core.urlresolvers import reverse

from api.models import Review, Project


class CommonReviewTests(object):
    '''
    Common tests for Lesson and Project Reviews.
    '''

    def test_must_have_rating(self):
        '''
        If a Review is posted without a rating, the server returns an error.
        '''

        obj = {
            'text': 'Review with no rating',
        }

        resp = self.client.post(self.api_list_url, json.dumps(
            obj,
            cls=DjangoJSONEncoder
        ), content_type='application/json')

        self.assertEqual(resp.status_code, 400)
        self.assertIn('rating', resp.data)

    def test_can_get_reviewed_item_info(self):
        '''
        Makes sure that the Review contains information about the 
        ReviewedItem.
        '''

        reviews = self.client.get(self.api_list_url).data['results']

        for review in reviews:

            self.assertIn('reviewedItem', review)
            self.assertIn('title', review['reviewedItem'])
            self.assertIn('id', review['reviewedItem'])
            self.assertIn('self', review['reviewedItem'])
            self.assertIn('type', review['reviewedItem'])

            self.assertEqual(review['reviewedItem']['type'], self.content_type)

            resp = self.client.get(review['reviewedItem']['self'])
            self.assertEqual(resp.status_code, 200)
            reviewedItem = resp.data

            self.assertEqual(reviewedItem['title'], review['reviewedItem']['title'])
            self.assertEqual(reviewedItem['id'], review['reviewedItem']['id'])

    def test_cant_double_review_item(self):
        '''
        If the user re-posts a review for a specific item, the backend
        should overwrite the first review and in no way let the user review the
        same item more than once.
        '''

        review = copy.deepcopy(self.object_to_post)

        resp = self.client.post(self.api_list_url, json.dumps(
            review,
            cls=DjangoJSONEncoder
        ), content_type='application/json')

        self.assertIn(resp.status_code, [200, 201, 202, 203])

        review['rating'] = 10
        review['text'] = 'ttt yyy xxx bbb aaa zzz'

        resp2 = self.client.post(self.api_list_url, json.dumps(
            review,
            cls=DjangoJSONEncoder
        ), content_type='application/json')

        self.assertIn(resp2.status_code, [200, 201, 202, 203])

        # Make sure that the reviewed item is the same for both objects.
        self.assertEqual(resp.data['reviewedItem'], resp2.data['reviewedItem'])

        reviews_in_db = Review.objects.filter(
            object_id=resp.data['reviewedItem']['id'],
            owner_id=resp.data['author']['id'],
            content_type__model=resp.data['reviewedItem']['type'],
        )

        # Make sure that there's only one Review in the DB for the user and the reviewed object.
        self.assertEqual(1, reviews_in_db.count())

        review_in_db = reviews_in_db[0]

        # Make sure that the latter rating and text took precedence over the former one
        self.assertEqual(review_in_db.rating, review['rating'])
        self.assertEqual(review_in_db.text, review['text'])

    def test_same_object_two_users(self):
        '''
        Make sure that the same object can be reviewed by 2 different users.
        '''

        # Get a review.
        review = self.client.get(self.api_list_url).data['results'][0]

        obj_reviews = Review.objects.filter(
            object_id=review['reviewedItem']['id'],
            content_type__model=review['reviewedItem']['type'],
        )
        obj_reviews_count = obj_reviews.count()

        # Get a user that didn't review the object that 'review' is reviewing.
        another_user = get_user_model().objects.exclude(
            id__in=obj_reviews.values_list('owner_id', flat=True)
        ).first()

        # Log in with that user.
        self.client.force_authenticate(another_user)

        # Write another review about the object
        resp = self.client.post(self.api_list_url, json.dumps(
            self.object_to_post,
            cls=DjangoJSONEncoder
        ), content_type='application/json')

        # Make sure request succeeded.
        self.assertIn(resp.status_code, xrange(200,205))

        # Make sure that the number of reviews for the object increased by 1.
        self.assertEqual(
            obj_reviews_count + 1,
            Review.objects.filter(
                object_id=review['reviewedItem']['id'],
                content_type__model=review['reviewedItem']['type'],
            ).count()
        )

    def test_same_user_two_objects(self):
        '''
        Make sure that the same user can review 2 different objects.
        '''

        content_type = getattr(self, 'content_type')

        self.client.force_authenticate(self.global_user)
        
        # Get all of the logged in user's reviews.
        user_reviews = Review.objects.filter(
            owner_id=self.global_user.id,
            content_type__model=content_type,
        )
        user_reviews_count = user_reviews.count()

        reviewed_model = user_reviews.first().content_type.model_class()

        # Make sure the user already has reviews
        self.assertGreaterEqual(user_reviews_count, 1)

        # Get an unreviewed object, that the user surely has access to it.
        unreviewed_qs = reviewed_model.objects.exclude(id__in=Review.objects.filter(
                Q(owner=self.global_user) &
                Q(content_type__model=content_type)
            ).values_list('object_id')
        )
        if self.content_type == 'project':
            unreviewed_qs = unreviewed_qs.filter(publish_mode=Project.PUBLISH_MODE_PUBLISHED)
        obj = unreviewed_qs.first()

        # Write a review for that object
        resp = self.client.post(
            re.sub(r'/[0-9]+/reviews/$', '/%s/reviews/' % obj.id, self.api_list_url),
            json.dumps(
                self.object_to_post,
                cls=DjangoJSONEncoder
            ), content_type='application/json'
        )

        # Make sure request succeeded.
        self.assertIn(resp.status_code, xrange(200,205))

        # Make sure that the number of reviews by the user increased by one
        self.assertEqual(
            user_reviews_count + 1,
            Review.objects.filter(
                owner_id=self.global_user.id,
                content_type__model=content_type,
            ).count()
        )

    def test_get_and_create_reviews_for_preview_mode(self):

        #subject object is project
        subject_obj = getattr(self, 'project', None)
        self.assertNotEqual(subject_obj, None)
        
        project = subject_obj
        subject_obj_detail_url = reverse('api:project-detail', kwargs={'pk': subject_obj.id})

        # Make project locked:
        old_project_lock = project.lock
        project.lock = Project.BUNDLED
        project.save()

        self.client.force_authenticate(None)

        resp = self.client.get(subject_obj_detail_url)
        self.assertEqual(resp.status_code, 200)

        resp = self.client.get(self.api_list_url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], self.all_public_objects.count())

        # Cleanup
        project.lock = old_project_lock
        project.save()
