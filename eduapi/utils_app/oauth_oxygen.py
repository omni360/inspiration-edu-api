from oauthlib.oauth1 import *

class OauthClientWithEmptyToken(Client):
    def get_oauth_params(self, request):
        oauth_params = super(OauthClientWithEmptyToken, self).get_oauth_params(request)
        if self.resource_owner_key == '':
            oauth_params.append(('oauth_token', ''))
        return oauth_params
