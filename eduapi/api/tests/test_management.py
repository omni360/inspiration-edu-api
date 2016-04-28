from django.core.management import call_command
from django.core.management.base import CommandError
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.apps import apps
from django.utils import six
import unittest

class SetStaffUserManagementCommandTestCase(TestCase):
	MEMBER_ID = '1234567890'
	def setUp(self):
		super(SetStaffUserManagementCommandTestCase, self).setUp()
		# create user
		self.user_model = get_user_model()
		self.user = self.user_model.objects.create(member_id=self.MEMBER_ID, oxygen_id='098765432')

	def test_basic(self):
		# call command
		new_io = six.StringIO()
		call_command('set_staff_user',
					 stdout=new_io,
					 interactive=False,
					 member_id=self.MEMBER_ID,
					 password1='123',
					 password2='123')

		command_output = new_io.getvalue().strip()
		# verify success
		self.assertEqual(command_output,'Staff password created successfully')
		# verify user has staff priviliges
		user = self.user_model.objects.get(member_id=self.MEMBER_ID)
		self.assertEqual(user.is_staff,True)

	def test_missing_params(self):
		# call command with missing password
		new_io = six.StringIO()
		with self.assertRaises(CommandError):
			call_command('set_staff_user',
						 stdout=new_io,
						 interactive=False,
						 member_id=self.MEMBER_ID,
						 password1='123')

	def test_user_does_not_exist(self):
		# call command with none existing user
		new_io = six.StringIO()
		with self.assertRaises(CommandError):
			call_command('set_staff_user',
						 stdout=new_io,
						 interactive=False,
						 member_id='aaaaaaa', # user that does is not supposed to exist
						 password1='123',
						 password2='123')

	

