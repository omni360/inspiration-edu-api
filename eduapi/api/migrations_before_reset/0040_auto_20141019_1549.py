# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


def forwards_func(apps, schema_editor):

    # We get the model from the versioned app registry;
    # if we directly import it, it'll be the wrong version
    IgniteUser = apps.get_model("api", "IgniteUser")
    db_alias = schema_editor.connection.alias

    for user in IgniteUser.objects.all():
        if user.guardian:
            user.guardians.add(user.guardian)
            user.save()

def backwards_func(apps, schema_editor):

    # We get the model from the versioned app registry;
    # if we directly import it, it'll be the wrong version
    IgniteUser = apps.get_model("api", "IgniteUser")
    db_alias = schema_editor.connection.alias

    for user in IgniteUser.objects.all():
        if user.guardians.count():
            user.guardian = user.guardians.first()
            user.save()

class Migration(migrations.Migration):

    dependencies = [
        ('api', '0039_igniteuser_is_approved'),
    ]

    operations = [
        migrations.AddField(
            model_name='igniteuser',
            name='guardians',
            field=models.ManyToManyField(related_name=b'wards', to=settings.AUTH_USER_MODEL),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='igniteuser',
            name='guardian',
            field=models.ForeignKey(related_name=b'wards_old', blank=True, to=settings.AUTH_USER_MODEL, null=True),
        ),
        migrations.RunPython(
            forwards_func,
            reverse_code=backwards_func,
        ),
        migrations.RemoveField(
            model_name='igniteuser',
            name='guardian',
        ),
    ]
