import optparse
from django.core.management.base import BaseCommand

from api.models import Classroom


class Command(BaseCommand):
    help = ''''Temporary command that migrates database images from path:
    https://s3.amazonaws.com/<s3-bucket-name>/front-end/images/default-banner.jpg

    to 

    https://s3.amazonaws.com/<s3-bucket-name>/front-end/images/static/default-banner.jpg

    and from 

    https://s3.amazonaws.com/<s3-bucket-name>/front-end/images/default-thumbnail.jpg

    to 

    https://s3.amazonaws.com/<s3-bucket-name>/front-end/images/static/default-thumbnail.jpg

    The first migration is for Classroom banner images and the second is for Classroom card images.

    IMPORTANT: This is a temporary command that should be removed after the migration is finished.
    '''

    option_list = BaseCommand.option_list + (
        optparse.make_option(
            '--env',
            action='store',
            dest='env',
            default='prod',
            help='Whether prod or dev.'
        ),
    )

    def handle(self, *args, **options):

        print options['env']
        if options['env'] == 'prod':
            base_url = 'https://s3.amazonaws.com/ignite-uploads-prod-1/'
        elif options['env'] == 'dev':
            base_url = 'https://s3.amazonaws.com/ignite-site-dev/'
        else:
            return
        
        print 'Migrating Classroom banner images'
        for classroom in Classroom.objects.filter(banner_image__icontains='/default-banner.jpg'):
            if '/front-end/' in classroom.banner_image:
                classroom.banner_image = base_url + 'defaults/default-banner.jpg'
                classroom.save()

        print 'Migrating Classroom card images'

        for classroom in Classroom.objects.filter(card_image__icontains='/default-thumbnail.jpg'):
            if '/front-end/' in classroom.card_image:
                classroom.card_image = base_url + 'defaults/default-thumbnail.jpg'
                classroom.save()

        print 'Done!'
