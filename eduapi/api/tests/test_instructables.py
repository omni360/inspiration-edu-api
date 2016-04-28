from django.test import TestCase, Client
from django.core.urlresolvers import reverse

import httpretty

class InstructablesTestCase(TestCase):

    @httpretty.activate
    def test_instructables_proxy_view_correctly_forwards_request(self):

        c = Client()

        inst_id = 'asfkjh12391-._19238123asdfWE'
        expected_response = 'Everything works!!!'

        httpretty.register_uri(
            httpretty.GET,
            'http://www.instructables.com/json-api/showInstructable?id=%s' % inst_id,
            body=expected_response,
            content_type='application/json',
        )

        resp = c.get(reverse('instructables-proxy') + '?id=%s' % inst_id)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, expected_response)


