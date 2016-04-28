# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


def forwards_func(apps, schema_editor):
    # We get the model from the versioned app registry;
    # if we directly import it, it'll be the wrong version
    IgniteUser = apps.get_model("api", "IgniteUser")
    db_alias = schema_editor.connection.alias

    for user in IgniteUser.objects.all():
        user.oxygen_id = user.id
        user.save()


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0035_igniteuser_is_child'),
    ]

    operations = [
        migrations.AddField(
            model_name='igniteuser',
            name='oxygen_id',
            field=models.CharField(default=1, help_text=b'The Oxygen Member ID', max_length=50),
            preserve_default=False,
        ),
        migrations.RunPython(
            forwards_func,
            reverse_code=lambda apps, schema_editor: None
        ),
    ]
