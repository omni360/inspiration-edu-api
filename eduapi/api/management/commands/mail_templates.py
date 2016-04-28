import optparse
from django.core.management.base import BaseCommand, CommandError

from api.tasks import SendMailTemplate


class Command(BaseCommand):
    help = 'Manages the sendwithus mail templates task.'
    option_list = BaseCommand.option_list + (
        optparse.make_option(
            '--purge',
            action='store_true',
            dest='purge',
            default=False,
            help='Purge the templates and get fresh data from server the next time required.'
        ),
        optparse.make_option(
            '--refresh-now',
            action='store_true',
            dest='refresh_now',
            default=False,
            help='Refresh the mail templates from the server now.'
        ),
        optparse.make_option(
            '--set-refresh-threshold',
            action='store',
            dest='refresh_threshold_hours',
            default=None,
            help='Set refresh threshold hours to consider templates data from the server as stale.'
        ),
    )

    def handle(self, *args, **options):
        if options['purge']:
            SendMailTemplate.purge_templates()
            print 'Mail templates were purged. Next time they\'re needed, they will be fetched fresh from the server.'
        elif options['refresh_threshold_hours'] is not None:
            try:
                hours = int(options['refresh_threshold_hours'])
            except ValueError:
                raise CommandError('Invalid number of hours of refresh threshold (must be integer)!')
            SendMailTemplate.set_refresh_threshold(hours)
            print 'Mail templates refresh threshold is set to %d hours.' %(hours,)
        else:
            print 'Templates list:'
            templates_dict = SendMailTemplate.get_templates(force_refresh=options['refresh_now'])
            for template_name, template in templates_dict.items():
                print ' '*4 + template_name
            templates_info = SendMailTemplate.get_templates_info()
            print '* templates loaded at: %s' %(templates_info['load_time'],)
            print '* templates refresh threshold: %d hours' %(templates_info['refresh_threshold_hours'])
