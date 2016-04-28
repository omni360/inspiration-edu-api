# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

import string
from utils_app.hash import generate_code as generate_code_base


def forward_default_classroom_codes(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    Classroom = apps.get_model('api', 'Classroom')

    #go over all classrooms, and generate an initial code:
    classrooms_list = Classroom.objects.using(db_alias).all()
    for classroom in classrooms_list:
        if classroom.code:
            continue
        #Note: Classroom.generate_code is not defined via apps.get_model, so use the internals of it:
        classroom.code = generate_code_base(8, chars=string.ascii_uppercase + string.digits)
        classroom.save(using=db_alias)

def backward_default_classroom_codes(apps, schema_editor):
    #do nothing - not reversible
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0007_auto_20150528_1730'),
    ]

    operations = [
        migrations.RunPython(
            forward_default_classroom_codes,
            backward_default_classroom_codes
        )
    ]
