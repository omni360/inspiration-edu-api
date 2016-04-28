# import Cookie
import re
from django.core.urlresolvers import reverse


class IgnoreBadCookies(object):
    '''
    Due to Python bug in parsing cookies (2.7.9 or 3.4 and above, earlier versions were ok), if a cookie contains a [ character
    in the cookie value, everything beyond that cookie is ignored.
    This middleware ignores all the bad cookies in HTTP_COOKIE string, by replacing the HTTP_COOKIE string with a string
    that does not contain those "bad" characters.
    Therefore, this middleware must be called before any use of request.COOKIES.

    When Python (or Django) will resolve this bug, this middleware can be removed.

    See: http://bugs.python.org/issue22931
    See: https://code.djangoproject.com/ticket/24492

    This bug caused /admin/ pages to result in CSRF Validation Error.
    '''

    def process_request(self, request):
        #remove all "bad" cookies from the HTTP_COOKIE string:
        bad_cookie_patt = re.compile(r'\s*[^;=]+\s*=\s*[^;]*[\[\]][^;]*(\s+|;|$)')
        if request.environ.has_key('HTTP_COOKIE'):
            request.environ['HTTP_COOKIE'] = bad_cookie_patt.sub('', request.environ.get('HTTP_COOKIE', ''))
