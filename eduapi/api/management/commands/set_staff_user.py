import sys
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.apps import apps
from optparse import make_option
from getpass import getpass


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--interactive',
                    dest='interactive',
                    default=True,
                    help='Lets you choose user and provide password'),
        ) + (
        make_option('--member_id',
                    dest='member_id',
                    default='',
                    help='Set params manually. Do not forget to disable interactive'),
        ) + (
        make_option('--password1',
                    dest='password1',
                    default='',
                    help='Set params manually. Do not forget to disable interactive'),
        ) + (
        make_option('--password2',
                    dest='password2',
                    default='',
                    help='Set params manually. Do not forget to disable interactive'),
        )

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.user_model = get_user_model()

    def handle(self, *args, **options):

        print(options)

        interactive = options['interactive']

        if not interactive:
            member_id = options.get('member_id', None)
            password1 = options.get('password1', None)
            password2 = options.get('password2', None)
            if all([member_id, password1, password2]):
                if password1 != password2:
                    self.stderr.write("Error: Your passwords didn't match.")
                    return
                self.set_user_staff_password(member_id, password1)
            else:
                raise CommandError('user and password fields were not passed')
        else:
            member_id = raw_input('Please enter the member id of the user to give staff permissions to:\n')
            password1 = getpass('Enter a staff password for this account:')
            password2 = getpass('retype password:')
            # confirm passwords
            if password1 != password2:
                self.stderr.write("Error: Your passwords didn't match.")
                return
            self.set_user_staff_password(member_id, password1)


    def set_user_staff_password(self, member_id, password):
        try:
            # get user model
            user = self.user_model.objects.get(member_id=member_id)
            user.set_password(password)
            user.is_staff = True
            user.is_superuser = True
            user.save()
            self.stdout.write("Staff password created successfully")

        except self.user_model.DoesNotExist:
            raise CommandError("Ignite user does not exist")
