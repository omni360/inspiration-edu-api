# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


def migrate_fix_order_dups_forwards(apps, schema_editor):
    Instruction = apps.get_model('api', 'Instruction')
    Step = apps.get_model('api', 'Step')

    steps_with_dup_instruction_order_pk_list = Instruction.objects.values('step', 'order').annotate(dups=models.Count('pk')).values_list('step', flat=True).filter(dups__gt=1).distinct()
    steps_with_dup_instruction_order = Step.objects.filter(pk__in=steps_with_dup_instruction_order_pk_list)

    for step_with_dup in steps_with_dup_instruction_order:
        ordered_instructions = step_with_dup.instructions.all().order_by('-order', 'added')
        for idx, inst in enumerate(ordered_instructions):
            inst.order = idx
            inst.save()

def migrate_fix_order_dups_backwards(apps, schema_editor):
    pass  #noop


class AlterUniqueTogetherDeferrable(migrations.AlterUniqueTogether):
    def database_forwards(self, app_label, schema_editor, from_state, to_state, backwards=False):
        old_sql_create_unique = schema_editor.sql_create_unique
        if not backwards:
            schema_editor.sql_create_unique += 'DEFERRABLE INITIALLY IMMEDIATE'
        super(AlterUniqueTogetherDeferrable, self).database_forwards(app_label, schema_editor, from_state, to_state)
        schema_editor.sql_create_unique = old_sql_create_unique

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        self.database_forwards(app_label, schema_editor, from_state, to_state, backwards=True)


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0004_auto_20150421_0909'),
    ]

    operations = [
        migrations.AddField(
            model_name='instruction',
            name='image',
            field=models.URLField(help_text=b'A URL of an image that will accompany the instruction', null=True, blank=True),
            preserve_default=True,
        ),

        migrations.AlterModelOptions(
            name='instruction',
            options={'ordering': ('step', 'order')},
        ),
        migrations.AlterModelOptions(
            name='step',
            options={'ordering': ('lesson', 'order')},
        ),

        migrations.RunPython(
            code=migrate_fix_order_dups_forwards,
            reverse_code=migrate_fix_order_dups_backwards,
        ),

        ###remove regular unique together, and use custom unique together deferrable:
        # migrations.AlterUniqueTogether(
        #     name='instruction',
        #     unique_together=set([('step', 'order')]),
        # ),
        migrations.AlterUniqueTogether(
            name='step',
            unique_together=set(),
        ),

        ###unique together deferrable:
        AlterUniqueTogetherDeferrable(
            name='step',
            unique_together=set([('lesson', 'order')]),
        ),
        AlterUniqueTogetherDeferrable(
            name='instruction',
            unique_together=set([('step', 'order')]),
        ),
    ]
