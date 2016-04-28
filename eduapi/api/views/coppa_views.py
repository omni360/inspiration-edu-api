import urlparse
import requests
from urllib import urlencode
from django_redis import get_redis_connection

from django.conf import settings
from django.http import HttpResponseRedirect

from rest_framework import status, serializers, exceptions
from rest_framework.views import APIView
from rest_framework.reverse import reverse
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer, StaticHTMLRenderer

from rest_framework.authentication import TokenAuthentication

from ..auth.oxygen_operations import OxygenOperations
from .permissions import IsNotChild
from .authentication import RedisAuthentication


class VerifyAdulthood(APIView):
    '''
    This view is responsible for verifying that a user is an adult and for
    authorizing children and linking them to their moderators.

    This view does this using the 'post' and 'get' methods below. The methods'
    documentations describe the process thoroughly.
    '''

    class VerifyAdulthoodSerializer(serializers.Serializer):
        '''Used for getting & validating the input of the POST method'''
        authorizationCode = serializers.CharField(source='authorization_code', required=True)
        sessionId = serializers.CharField(source='session_id', required=True)
        secureSessionId = serializers.CharField(source='secure_session_id', required=True)

    class UserValidationException(Exception):
        '''Exception for the VerifyAdulthood view'''
        pass

    class RedirectAuthError(exceptions.APIException):
        '''User didn't validate, redirect the user instead of returning 401'''
        pass

    # "Constants"
    HASH_PREFIX = RedisAuthentication.REDIS_AUTH_PREFIX
    INVALID_AUTHORIZATION_CODE = 'ID-CC-015'
    USER_DIDNT_LOG_IN_WITH_AUTH_CODE = 'ID-CC-017'
    AUTH_CODE_EXPIRED = 'ID-CC-019'
    PAYMENT_AMOUNT = 0.5
    error_reasons = {
        USER_DIDNT_LOG_IN_WITH_AUTH_CODE: 'It seems like there was a problem with your log in process. Try to log out and use the link in the email to log in again.',
        AUTH_CODE_EXPIRED: 'Your link has expired. Ask your child to sign up again and approve him/her within 7 days.',
    }

    # APIView declarative behavior
    serializer_class = VerifyAdulthoodSerializer
    authentication_classes = (TokenAuthentication, RedisAuthentication,)
    permission_classes = (IsNotChild,)
    renderer_classes = (JSONRenderer, StaticHTMLRenderer,)

    # Used to store the Redis connection.
    redis = None

    def handle_exception(self, exc):
        '''
        Handle our specific RedirectAuthError or delegate to super.
        '''

        if isinstance(exc, self.RedirectAuthError):
            return self.get_response_with_error(
                errors='Failed to validate, your session might have expired'
            )
        else:
            return super(VerifyAdulthood, self).handle_exception(exc)

    def permission_denied(self, request):
        '''
        If this is an HTML GET request, then don't return the usual
        401, instead, redirect the user with the appropriate error message.

        The reason is that the problem might be that the user's Redis record 
        has expired. In that case, we'd want the user to get a proper message.
        '''

        if request.method == 'GET':
            raise self.RedirectAuthError()

        return super(VerifyAdulthood, self).permission_denied(request)

    def get_redis(self):
        '''Creates a redis connection and returns it'''

        if not self.redis:
            self.redis = get_redis_connection('default')
        return self.redis

    def make_paypal_request(self, params):
        '''
        Helper method for making requests to Paypal.

        Performs common configuration of request and basic validation of 
        response.
        '''

        # Make request using basic params + params from method arguments.
        resp = requests.get(
            settings.PAYPAL_NVP_BASE_URL, params=dict({
            'USER': settings.PAYPAL_USERNAME,
            'PWD': settings.PAYPAL_PASSWORD,
            'SIGNATURE': settings.PAYPAL_SIGNATURE,
            'VERSION': settings.PAYPAL_VERSION,
        }.items() + params.items()))

        # Validate request

        if resp.status_code != 200:
            return resp.text, 'Request failed'

        resp = urlparse.parse_qs(resp.text)

        if resp['ACK'][0] != 'Success':
            return resp, ('Paypal returned Failure')

        # Return body of response converted to Python dictionary.
        return resp, None

    def authorize_child(
            self, 
            guardian,
            authorization_code,
            session_id,
            secure_session_id,
            redis_hash,
        ):
        '''
        Helper method for authorizing a child with the Oxygen API.

        Motivation:
        ==========
        The Oxygen API is pretty complicated with a lot of edge cases.
        There are two scenarios in which we are required to authorize a child
        in the API:
            1. In the POST method, if the user is already a verified adult.
            2. In the GET method, if the user just returned from Paypal. This 
               is done after the Paypal transaction verification.

        Because of that, we moved the section that's responsible for the 
        authorization with Oxygen into this separate helper method.

        What the method does:
        ====================
        Oxygen verification is composed of two steps:
            1. Linking the parent with the child, using an authorization_code.
            2. Authorizing the child for regular use.

        In between these steps, various errors could occur. We try to overcome 
        errors as much as we can or provide appropriate feedback.
        '''

        #use OxygenOperations to add children to the guardian:
        oxygen_operations = OxygenOperations()
        try:
            oxygen_operations.authorize_and_approve_guardian_child(guardian, authorization_code, redis_hash)
        except oxygen_operations.OxygenRequestFailed as exc:
            r_exc = self.UserValidationException()
            #use custom error message if defined:
            r_exc.reason = self.error_reasons[exc.oxygen_error_code] if self.error_reasons.get(exc.oxygen_error_code, None) else exc.message
            raise r_exc

    def post(self, request, *args, **kwargs):
        '''
        This function is called in two scenarios:
            1. The parent needs to be verified as an adult using Paypal.
            2. The parent's adulthood is verified, a child needs to be 
               authorized.

        In the first scenario, we prepare a Paypal transaction of 
        PAYMENT_AMOUNT USD. This transaction serves as proof that the user is
        an adult. We then redirect the user to Paypal to make the transaction.
        Note that we don't actually return a redirect status code, since this 
        is an AJAX call, we send back the URL to redirect to and the client
        handles the redirect.

        In the second scenario, we use 'authorize_child' in order to authorize
        the child with the Oxygen API.
        '''

        # Parse the request body using the serializer and make sure it's valid.
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Input is valid, fetch it.
        authorization_code = serializer.validated_data['authorization_code']
        session_id = serializer.validated_data['session_id']
        secure_session_id = serializer.validated_data['secure_session_id']

        # Since the user is redirected to Paypal and back again to this view,
        # we need to create a method for logging the user back in without the
        # Authorization header. The reason is that we don't want to pass the
        # API Token to Paypal, or in the URL string in general, and we want 
        # Paypal to redirect the user straight to the backend, without going
        # through the front end.
        # 
        # So we make a hash for logging in. The hash is the key to a Redis
        # hash object that stores enough info about the user to log her back 
        # in. This object is used for storing other information as well.
        # The object expires after one hour in order to not make it too easy
        # to break in.
        url_hash = RedisAuthentication.create_hash(request.user.id)
        redis_hash = self.HASH_PREFIX + url_hash

        # If user makes the request to just authorize a child.
        if request.user.is_verified_adult:
            try:
                # Authorize the child
                self.authorize_child(
                    request.user,
                    authorization_code,
                    session_id,
                    secure_session_id,
                    redis_hash,
                )

                # Success!
                return Response(data={'verifiedAuthCode': authorization_code})
            except self.UserValidationException, e:

                # Failure. Send default error or explanation from exception.
                error = getattr(e, 'reason', 'Failed to authorize child. Please try again later.')
                return Response(
                    status=status.HTTP_400_BAD_REQUEST,
                    data={'errors': {
                        'non_field_errors': [error],
                    }, }
                )

        # User needs to be authorized as adult.

        # Prepare a Paypal Express checkout URL. The user will be redirected to
        # this URL in order to make the transaction.
        resp, error = self.make_paypal_request(params={
            'METHOD': 'SetExpressCheckout',
            'PAYMENTREQUEST_0_PAYMENTACTION': 'SALE',
            'PAYMENTREQUEST_0_AMT': self.PAYMENT_AMOUNT,
            'PAYMENTREQUEST_0_CURRENCYCODE': 'USD',
            'PAYMENTREQUEST_0_DESC': 'A $%(amount)s transaction used to verify that you, %(name)s (%(email)s), are an adult' % {
                'amount': self.PAYMENT_AMOUNT,
                'name' : request.user.name,
                'email': request.user.email,
            },
            'cancelUrl': settings.IGNITE_FRONT_END_MODERATION_URL,
            'returnUrl': reverse(
                viewname='api:verify-adult-2nd-stage', 
                request=request,
                kwargs={'hash': url_hash}
            ),
        })

        if error:
            raise Exception('Failed to connect with PayPal')

        # Paypal prepared the transaction URL.

        # Store the user info in Redis in order to log the user back in using
        # a hash value from the Paypal return URL.
        r = self.get_redis()
        r.hmset(redis_hash, {
            'user_id': request.user.id,
            'authorization_code': authorization_code,
            'token': resp['TOKEN'][0],
            'session_id': session_id,
            'secure_session_id': secure_session_id,
        })
        r.expire(redis_hash, 60 * 60) # Expire in 1 hour

        # Send the Paypal link to the user.
        return Response(
            data={
                'redirect': settings.PAYPAL_BASE_URL + '/cgi-bin/webscr' + '?' + urlencode({
                    'cmd': '_express-checkout',
                    'token': resp['TOKEN'][0],
                })
            }
        )

    def get_response_with_error(self, errors=None, successes=None):
        '''
        Converts error and success messages into a response to the GET method.

        The response is a redirect response and the error\success messages are
        passed as query parameters in the URL.
        '''

        # Make sure 'errors' & 'successes' are lists of errors\success messages
        if errors and not isinstance(errors, list):
            errors = [errors]
        if successes and not isinstance(successes, list):
            successes = [successes]

        # Add error=errors and success=successes to the query params only if
        # not empty.
        params = {
            key: value
            for key, value
            in zip(('error', 'success',), (errors,successes,))
            if value
        }

        # Return the redirect response.
        return HttpResponseRedirect(
            settings.IGNITE_FRONT_END_MODERATION_URL +
            '?' + urlencode(params, True).replace('+','%20')
        )

    def get(self, request, hash):
        '''
        This function is called when Paypal redirects the user back from the
        transaction screen.

        Since Paypal redirects using a GET request, we make sure that it 
        redirects to the backend and not the front end.

        This function is responsible for:
            1. Validating the response from Paypal and making the transaction.
            2. Marking the user as adult, after verification is complete.
            2. Authorizing the child using 'authorize_child'.
        '''

        # The user is logged into the system using the hash in the URL and
        # the 'RedisAuthentication' authentication class. So at this point,
        # the user is already logged in.

        # Using the hash in the URL, get the object that we stored in Redis
        # in order to use data that was provided to us before the transition
        # to Paypal.
        r = self.get_redis()
        redis_hash = self.HASH_PREFIX + hash
        user_obj = r.hgetall(redis_hash) or {'token': '-'}

        # Check that the token in the URL matches the one we stored in Redis.
        if user_obj['token'] != request.QUERY_PARAMS.get('token', '$'):
            return self.get_response_with_error('Failed to make the transaction')

        # GetExpressCheckoutDetails - Get the details about the transaction.
        resp, error = self.make_paypal_request(params={
            'METHOD': 'GetExpressCheckoutDetails',
            'TOKEN': user_obj['token'],
        })

        if error:
            return self.get_response_with_error('Failed to make the transaction')

        # DoExpressCheckoutPayment - Make the actual Paypal transaction.
        resp, error = self.make_paypal_request(params={
            'METHOD': 'DoExpressCheckoutPayment',
            'TOKEN': user_obj['token'],
            'PAYERID': resp['PAYERID'][0],
            'PAYMENTREQUEST_0_AMT': self.PAYMENT_AMOUNT,
            'PAYMENTREQUEST_0_PAYMENTACTION': 'SALE',
            'PAYMENTREQUEST_0_CURRENCYCODE': 'USD',
        })

        if error:
            return self.get_response_with_error('Failed to make the transaction')

        # First of all, mark that the user is now an adult.
        request.user.is_verified_adult = True
        request.user.save()

        # Now, try to authorize the child in Oxygen.
        try:
            self.authorize_child(
                request.user,
                user_obj['authorization_code'],
                user_obj['session_id'],
                user_obj['secure_session_id'],
                redis_hash,
            )
        except self.UserValidationException, e:
            # Failed to authorize child, return error and success messages.
            error = getattr(e, 'reason', '') or 'Failed to authorize child, please try again later'
            return self.get_response_with_error(
                successes='Successfully verified that you\'re an adult',
                errors=error,
            )

        # Success! Return success response.
        return HttpResponseRedirect(
            settings.IGNITE_FRONT_END_MODERATION_URL +
            '?verifiedAuthorizationCode=' + user_obj['authorization_code']
        )
