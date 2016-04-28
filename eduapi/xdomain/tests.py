import re

from django.test import TestCase
from django.test import Client
from django.conf import settings
from django.core.urlresolvers import reverse
from django.contrib.staticfiles import finders

class XdomainTest(TestCase):


    def test_proxy_html_page_returns(self):

        c = Client()
        resp = c.get(reverse('xdomain:xdomain-proxy'))
        self.assertRegexpMatches(resp.content, r'^<!doctype html>')
        self.assertRegexpMatches(resp.content, r'<script src="(.+)xdomain/js/xdomain\.min\.js" data-master="\*"></script>')

    def test_proxy_static_script_downloadable(self):

        c = Client()
        resp = c.get(reverse('xdomain:xdomain-proxy'))
        script_url = re.search(r'src="' + settings.STATIC_URL + '(.+\.js)" data-master', resp.content).group(1)

        resp_script = c.get(script_url)
        result = finders.find(script_url)
        self.assertIsNotNone(result)


    def test_proxy_html_page_with_script(self):

        c = Client()
        resp = c.get(reverse('xdomain:xdomain-proxy'))
        self.assertEqual(resp.status_code, 200)

    def test_proxy_returns_without_x_frame_options(self):

        c = Client()

        resp = c.get(reverse('xdomain:xdomain-proxy'))

        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('X-Frame-Options', resp)
