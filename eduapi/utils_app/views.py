import requests

from django.http import HttpResponse
from utils_app.sanitize import sanitize_string

def instructables_proxy_view(request):
    """
    Sends a GET request to the url 'URL' and returns the result to the sender.

    We need this view to proxy requests to Autodesk's API because of the same 
    origin policy.
    """

    inst_id = sanitize_string(request.GET.get('id'))

    response = requests.get(
    	'http://www.instructables.com/json-api/showInstructable?id=%s' % inst_id
	)

    # Read the response 
    response_status = response.status_code
    response_headers = response.headers
    response_data = response.text

    return HttpResponse(
        response_data, 
        content_type=response_headers['Content-Type'], 
        status=response_status)
