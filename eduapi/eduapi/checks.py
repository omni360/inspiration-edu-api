from django.core.checks import register, Error, Warning, Info
import os

@register('settings')
def environmental_variables_check(app_configs, **kwargs):
    errors = []

    env_list = [
    	{ 'key' : 'DATABASE_URL', 'level' : Error },
    	{ 'key' : 'EDUAPI_ENV_DEBUG', 'level' : Warning },
    ]

    for index, env in enumerate(env_list):
    	if os.environ.get(env['key']) is None:
    		errors.append(env['level'](
    			'%s not defined as environmental variable' % env['key'],
    			hint='Check virtualenv postactivate script',
    			obj=None,
    			id='settings.%s' % index
    			))
    return errors