# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


def set_undecided_as_default(apps, schema_editor):
    IgniteUser = apps.get_model('api', 'IgniteUser')
    IgniteUser.objects.filter(user_type='other').update(user_type='undecided')

class Migration(migrations.Migration):

    dependencies = [
        ('api', '0037_lessonstate_extra'),
    ]

    operations = [
        migrations.AlterField(
            model_name='igniteuser',
            name='user_type',
            field=models.CharField(default=b'undecided', help_text=b'The user type', max_length=10, choices=[(b'teacher', b'Teacher'), (b'student', b'Student'), (b'parent', b'Parent'), (b'other', b'Other'), (b'undecided', b'Undecided')]),
        ),
        migrations.RunPython(set_undecided_as_default),
    ]
