from django.conf import settings
from django.core.urlresolvers import reverse

from rest_framework.test import APITestCase as DRFTestCase

from edu_api_test_case import EduApiTestCase

from api.views import ApiRoot

class ApiRootTests(DRFTestCase):

    longMessage = True
    api_root_url = reverse('api:root')

    def test_choices(self):
        """The root view returns the choices in the correct format"""
        
        resp = self.client.get(self.api_root_url)
        choices = resp.data['choices']
        
        # Check that the available choices sets are correct.
        self.assertSetEqual(
            set([c['name'] for c in ApiRoot.choices]),
            set(choices.keys()) - {'application', 'license', }
        )

        for choice in ApiRoot.choices:
            self.assertListEqual(
                [{'v': c_v, 'd': c_n} for c_v, c_n in choice['choices']],
                choices[choice['name']]
            )

        api_apps = sorted(choices['application'], key=lambda x: x['v'])
        settings_apps = sorted(settings.LESSON_APPS.values(), key=lambda x: x['db_name'])
        
        self.assertEqual(len(api_apps), len(settings_apps))
        for idx, s_app in enumerate(settings_apps):
            self.assertEqual(s_app['db_name'], api_apps[idx]['v'])
            self.assertEqual(s_app['display_name'], api_apps[idx]['d'])
            self.assertEqual(s_app['logo'], api_apps[idx]['logo'])
        

    def test_root_view_works(self):
        """The root view returns a basic valid response"""
        
        resp = self.client.get(self.api_root_url)

        self.assertEqual(resp.status_code, 200)

        keys = resp.data.keys()
        self.assertIn('featureFlags', keys)
        self.assertIn('choices', keys)
        self.assertIn('urls', keys)

    def test_urls(self):
        """The URLs that the Root View returns work"""
        
        resp = self.client.get(self.api_root_url)
        urls = resp.data['urls']

        for url in urls.values():
            url_resp = self.client.get(url)
            self.assertIn(url_resp.status_code, [200,401,403,301,302], msg=url)
