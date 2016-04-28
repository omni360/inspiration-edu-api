from rest_framework.authentication import TokenAuthentication, exceptions

class EduTokenAuthentication(TokenAuthentication):
    """
    Acts exactly like DRF's TokenAuthentication with one difference:
    Since we always need a user right after getting the token, we've added
    a select_related clause that pre-fetches the user object.
    """

    def authenticate_credentials(self, key):
        try:
            # This is where we added the select_related clause
            token = self.model.objects.select_related('user').get(key=key)
        except self.model.DoesNotExist:
            raise exceptions.AuthenticationFailed('Invalid token')

        if not token.user.is_active:
            raise exceptions.AuthenticationFailed('User inactive or deleted')

        return (token.user, token)
