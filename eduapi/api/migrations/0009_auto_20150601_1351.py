# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


def forward_shorten_title(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    Step = apps.get_model('api', 'Step')

    steps_list = Step.objects.using(db_alias).all()
    for step in steps_list:
        if len(step.title)>120:
            step.title = step.title[:120]
            step.save(using=db_alias)

def backward_shorten_title(apps, schema_editor):
    #do nothing - not reversible
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0008_auto_20150601_1320'),
    ]

    operations = [
        migrations.RunPython(
            forward_shorten_title,
            backward_shorten_title
        ),

        migrations.AlterField(
            model_name='step',
            name='title',
            field=models.CharField(help_text=b'The title as it will appear to the user', max_length=120),
            preserve_default=True,
        ),
    ]
