# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0040_project_extra'),
    ]

    operations = [
        migrations.AlterField(
            model_name='project',
            name='license',
            field=models.CharField(default=b'CC-BY-NC-SA 3.0', help_text=b'The license that this project operates under', max_length=30, choices=[(b'CC-BY-NC-SA 3.0', b'CC: Attribution-NonCommercial-ShareAlike 3.0 Unported'), (b'CC-BY-SA 3.0', b'CC: Attribution-ShareAlike 3.0 Unported'), (b'CC-BY-NC 3.0', b'CC: Attribution-NonCommercial 3.0 Unported'), (b'CC-BY 3.0', b'CC: Attribution 3.0 Unported'), (b'Public Domain', b'Public Domain')]),
        ),
    ]
