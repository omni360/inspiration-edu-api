import optparse
import json
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import dateparse

from utils_app.oxygen_requests import OxygenOauthRequests

from api.models import ChildGuardian


class Command(BaseCommand):
    help = 'Approves all children in the application to their moderators.'
    option_list = BaseCommand.option_list + (
        optparse.make_option(
            '--start-date',
            action='store',
            dest='start_date',
            default=None,
            help='Only children added from the given start date.'
        ),
        optparse.make_option(
            '--end-date',
            action='store',
            dest='end_date',
            default=None,
            help='Only children added until the given end date.'
        ),
        optparse.make_option(
            '--moderator-type',
            action='store',
            dest='moderator_type',
            type='choice',
            choices=[ch[0] for ch in ChildGuardian.MODERATOR_TYPE_CHOICES],
            default=None,
            help='Only children of the given moderator type.'
        ),
        optparse.make_option(
            '--children-ids',
            action='store',
            dest='children_ids',
            default=None,
            help='Only children in the given list (users ids separated by comma without spaces).'
        ),
        optparse.make_option(
            '--guardian-id',
            action='store',
            dest='guardian_id',
            type='int',
            default=None,
            help='Only children of the given moderator id.'
        ),
    )

    def handle(self, *args, **options):
        child_guardian_qs = ChildGuardian.objects.all()
        if options['start_date']:
            child_guardian_qs = child_guardian_qs.filter(added__gte=dateparse.parse_datetime(options['start_date']))
        if options['end_date']:
            child_guardian_qs = child_guardian_qs.filter(added__lt=dateparse.parse_datetime(options['end_date']))
        if options['moderator_type']:
            child_guardian_qs = child_guardian_qs.filter(moderator_type=options['moderator_type'])
        if options['children_ids']:
            child_guardian_qs = child_guardian_qs.filter(child__id__in=options['children_ids'].split(','))
        if options['guardian_id']:
            child_guardian_qs = child_guardian_qs.filter(guardian__id=options['guardian_id'])
        child_guardian_count = child_guardian_qs.count()
        if child_guardian_count == 0:
            print 'No child-guardian links were found.'
        else:
            proceed = raw_input('%d children-moderator links found to be approved in Oxygen. Are you sure (type \'yes\' to approve)? ' % (child_guardian_qs.count(),))
            if proceed == 'yes':
                ox_oauth_requests = OxygenOauthRequests()
                for child_guardian in child_guardian_qs:
                    #approve the child to the moderator:
                    approve_resp  = ox_oauth_requests.put(
                        url='/api/coppa/v1/moderator/%(moderator_id)s/child/%(child_id)s' % {
                            'moderator_id': child_guardian.guardian.oxygen_id,
                            'child_id': child_guardian.child.oxygen_id,
                        },
                        data=json.dumps({
                            'childAccount': {
                                'consumerKey': settings.OXYGEN_CONSUMER_KEY,
                                'childAccountStatus': 'Approved',
                            }
                        }),
                        headers={'content-type': 'application/json'},
                    )
                    if approve_resp.status_code == 200:
                        #mark child as approved (if not yet marked):
                        if not child_guardian.child.is_approved:
                            child_guardian.child.is_approved = True
                            child_guardian.child.save()
                        print '- Approved: [%d] %s' % (child_guardian.child.id, child_guardian.child.name)
                    else:
                        errmsg = 'unknown'
                        try:
                            errmsg = approve_resp.json()['error']['errorDescription']
                        except ValueError:
                            pass
                        print '- FAILED [%s]: [%d] %s' % (errmsg, child_guardian.child.id, child_guardian.child.name)
            else:
                print 'Aborted!'
