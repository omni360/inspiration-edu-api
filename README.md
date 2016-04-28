EDU API Backend
===============

The Backend and REST API supplier for the Autodesk Ignite project and other Autodesk and third party education content consumers.


Installation

* mkvirtualenv autodesk-edu-backend
* workon autodesk-edu-backend
* git clone repo
* pip install -r requirements.txt
    

* Create a new database using psql.
* Run: export DATABASE_URL=postgres://postgres:postgres@localhost:5432/[db_name]
* Run: export EDUAPI_ENV_DEBUG=TRUE (only in a dev environment)
* python manage.py migrate
* python manage.py runserver
