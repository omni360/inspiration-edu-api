from django.conf import settings
from .tasks import send_mail_template


def joined_classroom_email(classroom_state):
    '''
    Emails the guardians of the user in the classroom_state, telling her that 
    her child has joined the classroom.
    '''
    child = classroom_state.user
    guardians = child.guardians.all()
    classroom = classroom_state.classroom

    # prepare emails for all guardians of the child user:
    emails = []
    for guardian in guardians:

        # Don't send the email to this classroom's teacher.
        if guardian != classroom.owner:
            emails.append({
                'recipient': {
                    'name': guardian.name,
                    'address': guardian.email,
                },
                'email_data': {
                    'classroom_name': classroom.title,
                    'dashboard_url': settings.IGNITE_FRONT_END_MODERATION_URL,
                    'child_username': child.name,
                    'guardian_name': guardian.name,
                },
            })

    # send emails:
    if emails:
        send_mail_template.delay(settings.EMAIL_TEMPLATES_NAMES['CHILD_JOINED_CLASSROOM'], emails)


def invite_classroom_code(classroom, invitees, message=None):
    '''
    Emails all the invitees emails an invitation to a classroom using a classroom code.
    '''
    #validate that classroom has a code to send:
    if not classroom.code:
        return

    emails = []
    for invitee in invitees:
        emails.append({
            'recipient': {
                'address': invitee,
            },
            'email_data': {
                'classroom_name': classroom.title,
                'classroom_code': classroom.code,
                'classroom_code_display': '-'.join([classroom.code[i:i+4] for i in xrange(0, len(classroom.code), 4)]),
                'teacher_name': classroom.owner.name,
                'invitation_url': settings.IGNITE_FRONT_END_DASHBOARD_URL + 'myclassrooms/?joinclass=' + classroom.code,
                'message': message.replace('\n', '<br>\n') if message else '',
            },
        })

    # send emails:
    if emails:
        send_mail_template.delay(settings.EMAIL_TEMPLATES_NAMES['CLASSROOM_CODE'], emails)
