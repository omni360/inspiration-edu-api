import requests

from django.conf import settings

import oauth_oxygen


class OxygenOauthRequests(object):
    '''
    2-legged Oxygen OAuth1 authenticated requests.
    '''
    def __init__(self, session_id=None, secure_session_id=None):
        self.session_id = session_id
        self.secure_session_id = secure_session_id

    def get_2legged_signed_url(self, verb, url):
        ox_client = oauth_oxygen.OauthClientWithEmptyToken(
            settings.OXYGEN_CONSUMER_KEY,  #consumer key
            settings.OXYGEN_CONSUMER_KEY_SECRET,  #consumer key secret
            '',  #empty token
            '',  #empty token secret
            signature_type=oauth_oxygen.SIGNATURE_TYPE_QUERY,  #use oauth in URL query string
        )
        signed_url, _, _ = ox_client.sign(settings.OXYGEN_API + url, verb)
        return signed_url

    def get_3legged_signed_url(self, verb, url, session_id=None, secure_session_id=None):
        session_id = session_id or self.session_id
        secure_session_id = secure_session_id or self.secure_session_id

        if not session_id or not secure_session_id:
            raise ValueError('session_id and secure_session_id must be provided in constructor')

        # Get a signed URL from the Spark Drive API.
        resp = requests.get(
            settings.SPARK_DRIVE_API + '/API/V1/A360/SignURL',
            params={
                'url': settings.OXYGEN_API + url,
                'httpVerb': verb,
            },
            headers={
                'X-AFC': settings.SPARK_AFC,
                'X-Session': session_id,
                'X-Secure-Session': secure_session_id,
            },
        )
        if resp.status_code != 200:
            raise Exception('Couldn\'t sign Oxygen URL')
        signed_url = resp.json()['SIGNED_URL']
        return signed_url

    def _make_2legged_request(self, verb, url, *args, **kwargs):
        signed_url = self.get_2legged_signed_url(verb, url)
        return getattr(requests, verb.lower())(signed_url, *args, **kwargs)

    def get(self, url, *args, **kwargs):
        return self._make_2legged_request('GET', url, *args, **kwargs)

    def post(self, url, *args, **kwargs):
        return self._make_2legged_request('POST', url, *args, **kwargs)

    def put(self, url, *args, **kwargs):
        return self._make_2legged_request('PUT', url, *args, **kwargs)

    def patch(self, url, *args, **kwargs):
        return self._make_2legged_request('PATCH', url, *args, **kwargs)

    def delete(self, url, *args, **kwargs):
        return self._make_2legged_request('DELETE', url, *args, **kwargs)

    def _make_3legged_request(self, verb, url, *args, **kwargs):
        signed_url = self.get_3legged_signed_url(verb, url)
        return getattr(requests, verb.lower())(signed_url, *args, **kwargs)

    def get_3legged(self, url, *args, **kwargs):
        return self._make_3legged_request('GET', url, *args, **kwargs)

    def post_3legged(self, url, *args, **kwargs):
        return self._make_3legged_request('POST', url, *args, **kwargs)

    def put_3legged(self, url, *args, **kwargs):
        return self._make_3legged_request('PUT', url, *args, **kwargs)

    def patch_3legged(self, url, *args, **kwargs):
        return self._make_3legged_request('PATCH', url, *args, **kwargs)

    def delete_3legged(self, url, *args, **kwargs):
        return self._make_3legged_request('DELETE', url, *args, **kwargs)


#TODO: Use ClientWithEmptyToken to produce singed urls also for 3-legged.
# and don't use Shelly's backend anymore to reduce http requests.
# Update - Aborted: Since login is through Shelly's API, the token+secret are kept on Shelly's side,
#       and we can not produce 3-legged signed urls without token+secret. Thus, use Shelly's API to
#       get 3-legged signed urls.
# Note: sessionId and secureSessionId are credentials to Shelly's API, not to Oxygen.
