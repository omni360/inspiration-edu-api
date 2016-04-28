#!/usr/bin/env python
import os
import sys

if __name__ == "__main__":
	os.environ.setdefault("DJANGO_SETTINGS_MODULE", "eduapi.settings")

	from django.core.management import execute_from_command_line
	# allow the custome mockredis option to execute, then remove from argument list
	if '--mockredis' in sys.argv:
		import redis, fakeredis
		redis.StrictRedis = fakeredis.FakeStrictRedis
		sys.argv.remove('--mockredis')

	execute_from_command_line(sys.argv)
