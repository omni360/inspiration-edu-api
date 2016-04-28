# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0057_auto_20160111_0800'),
    ]

    operations = [
        migrations.AddField(
            model_name='igniteuser',
            name='parent_email',
            field=models.EmailField(help_text=b'The parent email child entered during registration', max_length=254, null=True, blank=True),
        ),
    ]
