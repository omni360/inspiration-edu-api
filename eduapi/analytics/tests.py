from django.core.cache import cache
from django.core.urlresolvers import reverse
from django.db.models import Count

from rest_framework.test import APITestCase
from api.models import Project


class AnalyticsTests(APITestCase):
    fixtures = ['test_projects_fixture_1.json']

    @classmethod
    def setUpTestData(cls):
        cls.project = Project.objects.annotate(registrations_count=Count('registrations')).filter(
            publish_mode=Project.PUBLISH_MODE_PUBLISHED,
            registrations_count__gt=0
        ).first()

    def test_api_get_analytics_data_data_placed_in_cache(self):
        self.client.force_authenticate(self.project.owner)
        response = self.client.get(reverse('api:project-analytics',
                                           kwargs={'pk': self.project.id,}))
        self.assertEquals(response.status_code, 200)
        self.assertIsNotNone(cache.get('project_analytics_%s' % self.project.id))

    def test_get_analytics_data_forbidden_for_authentication(self):
        response = self.client.get(reverse('api:project-analytics',
                                           kwargs={'pk': self.project.id,}))
        self.assertEquals(response.status_code, 401)
