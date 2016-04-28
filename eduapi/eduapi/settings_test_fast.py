from .settings import *

MIGRATION_MODULES = {'api': 'api.not_existing_migrations'}

try:
    NOSE_ARGS.remove('--with-coverage')
except:
    pass
