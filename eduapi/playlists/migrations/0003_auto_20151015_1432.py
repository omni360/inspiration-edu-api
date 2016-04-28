# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('playlists', '0002_playlist_playlist_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='playlist',
            name='playlist_type',
            field=models.CharField(default=b'other', help_text=b'Setting the playlist as Homepage will change the current Homepage playlist', max_length=20, choices=[(b'other', b'Other'), (b'featured', b'Featured'), (b'homepage', b'Homepage'), (b'new_student', b'New Student Homepage')]),
        ),
    ]
