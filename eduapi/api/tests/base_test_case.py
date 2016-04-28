import mock
import json

from ..tasks import send_mail_template

def mock_sendwithus_templates():
    """Mock for returning SendWithUs templates."""

    templates_names = [
        'Child joined classroom',
        'IGNITE_classroom_code',
        'IGNITE_classroom_invitation',
        'IGNITE_delegate_invitation',
        'IGNITE_notification_general',
        'IGNITE_notification_publish_mode_change',
        'IGNITE_arduino_kit_purchase_notification',
        'IGNITE_projects_in_review_summary',
    ]

    response = mock.Mock()

    response.status_code = 200
    response.body = json.dumps([{
        'name': template_name,
        'id': i,
    } for i, template_name in enumerate(templates_names)])
    response.json = lambda: json.loads(response.body)
    return response
def mock_sendwithus_send():
    pass

class BaseTestCase(object):
    
    def setUp(self, *args, **kwargs):
        super(BaseTestCase, self).setUp()
        send_mail_template.app.conf.CELERY_ALWAYS_EAGER = True

    def tearDown(self):
        super(BaseTestCase, self).tearDown()
        send_mail_template.app.conf.CELERY_ALWAYS_EAGER = False
