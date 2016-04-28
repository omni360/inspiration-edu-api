# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.contrib.postgres.fields


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0052_merge'),
    ]

    operations = [
        migrations.RenameField(
            model_name='project',
            old_name='teacher_info',
            new_name='teacher_additional_resources',
        ),
        migrations.AddField(
            model_name='project',
            name='ccss',
            field=django.contrib.postgres.fields.ArrayField(size=None, null=True, base_field=models.CharField(max_length=10, choices=[(b'RL', b'Reading Literature'), (b'RI', b'Reading Informational Text'), (b'RF', b'Reading Foundational Skills'), (b'W', b'Writing'), (b'SL', b'Speaking & Listening'), (b'L', b'Language'), (b'RST', b'Reading Science & Technical Subjects'), (b'WHST', b'Writing in History, Science, & Technical Subjects'), (b'CC', b'Counting and Cardinality'), (b'OA', b'Operations & Algebraic Thinking'), (b'NBT', b'Number & Operation in Base Ten'), (b'NF', b'Number & operations-Fractions'), (b'MD', b'Measurement and Data'), (b'G', b'Geometry'), (b'RP', b'Ratios and Proportional Relationships'), (b'NS', b'Number System'), (b'EE', b'Expressions and Equations'), (b'F', b'Functions'), (b'SP', b'Statistics and Probability'), (b'MP', b'Math Practices')]), blank=True),
        ),
        migrations.AddField(
            model_name='project',
            name='four_cs_collaboration',
            field=models.TextField(help_text=b'4 cs collaboration', max_length=250, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='project',
            name='four_cs_communication',
            field=models.TextField(help_text=b'4 cs communication', max_length=250, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='project',
            name='four_cs_creativity',
            field=models.TextField(help_text=b'4 cs creativity', max_length=250, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='project',
            name='four_cs_critical',
            field=models.TextField(help_text=b'4 cs critical', max_length=250, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='project',
            name='grades_range',
            field=django.contrib.postgres.fields.ArrayField(size=None, null=True, base_field=models.CharField(max_length=10, choices=[(b'K', b'K'), (b'1', b'1'), (b'2', b'2'), (b'3', b'3'), (b'4', b'4'), (b'5', b'5'), (b'6', b'6'), (b'7', b'7'), (b'8', b'8'), (b'9', b'9'), (b'10', b'10'), (b'11', b'11'), (b'12', b'12')]), blank=True),
        ),
        migrations.AddField(
            model_name='project',
            name='learning_objectives',
            field=django.contrib.postgres.fields.ArrayField(size=None, null=True, base_field=models.CharField(max_length=25), blank=True),
        ),
        migrations.AddField(
            model_name='project',
            name='ngss',
            field=django.contrib.postgres.fields.ArrayField(size=None, null=True, base_field=models.CharField(max_length=10, choices=[(b'PS1', b'Matter and Its Interactions'), (b'PS2', b'Motion and Stability: Forces and Interactions'), (b'PS3', b'Energy'), (b'PS4', b'Waves and Their Applications in Technologies for Information Transfer'), (b'LS1', b'From Molecules to Organisms: Structures and Processes'), (b'LS2', b'Ecosystems: Interactions, Energy, and Dynamics'), (b'LS3', b'Heredity: Inheritance and Variation of Traits'), (b'LS4', b'Biological Evolution: Unity and Diversity'), (b'ESS1', b"Earth's Place in the Universe"), (b'ESS2', b"Earth's Systems"), (b'ESS3', b'Earth and Human Activity'), (b'ETS1', b'Engineering Design'), (b'ETS2', b'Links Among Engineering, Technology, Science, and Society')]), blank=True),
        ),
        migrations.AddField(
            model_name='project',
            name='prerequisites',
            field=models.TextField(default=b'', max_length=1000, null=True, help_text=b'Course prerequisites', blank=True),
        ),
        migrations.AddField(
            model_name='project',
            name='skills_acquired',
            field=django.contrib.postgres.fields.ArrayField(size=None, null=True, base_field=models.CharField(max_length=25), blank=True),
        ),
        migrations.AddField(
            model_name='project',
            name='subject',
            field=django.contrib.postgres.fields.ArrayField(size=None, null=True, base_field=models.CharField(max_length=25, choices=[(b'art', b'Art'), (b'drama', b'Drama'), (b'geography', b'Geography'), (b'history', b'History'), (b'language art', b'Language Arts'), (b'math', b'Math'), (b'music', b'Music'), (b'science', b'Science'), (b'social studies', b'Social Studies'), (b'technology', b'Technology')]), blank=True),
        ),
        migrations.AddField(
            model_name='project',
            name='teacher_tips',
            field=models.TextField(default=b'', max_length=1000, null=True, help_text=b'Tips for teachers', blank=True),
        ),
        migrations.AddField(
            model_name='project',
            name='technology',
            field=django.contrib.postgres.fields.ArrayField(size=None, null=True, base_field=models.CharField(max_length=25, choices=[(b'3d printing', b'3D Printing'), (b'electronics', b'Electronics'), (b'3d design', b'3D Design')]), blank=True),
        ),
    ]
