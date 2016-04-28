import optparse
import re
import markdown
import cgi
from django.core.management.base import BaseCommand, CommandError
from django.db.models.loading import get_model
from django.db.models.fields import TextField

from utils_app import sanitize


class Command(BaseCommand):
    help = 'Converts model field from plain text (or markdown with --from-markdown) into HTML.'
    args = '<model> <field>'
    option_list = BaseCommand.option_list + (
        optparse.make_option(
            '--from-markdown',
            action='store_true',
            dest='from_markdown',
            default=False,
            help='Source field string is Markdown.'
        ),
        optparse.make_option(
            '--print-only',
            action='store_true',
            dest='print_only',
            default=False,
            help='Do not save objects back to DB, but only print the input/output strings.'
        ),
    )

    def _plain_text_to_html(self, text):
        #strip empty chars:
        text = text.strip()
        if not text:
            return ''

        #escape html chars:
        text = cgi.escape(text)

        #convert double new line to <p>:
        def par_br(matchobj):
            #inside paragraph, convert new line to <br>:
            par_text = matchobj.group(1)
            par_text = par_text.replace('\n', '<br />\n')
            return '<p>' + par_text + '</p>\n'
        pat1 = re.compile(r'(.*?)(\n\s*\n|$)', flags=re.DOTALL)
        text = pat1.sub(par_br, text)

        return text

    def _markdown_to_html(self, text):
        return markdown.markdown(text)

    def handle(self, *args, **options):
        #parse positional args:
        if len(args) != 2:
            raise CommandError('You must specify <model> and <field>.')
        model_name = args[0]
        field_name = args[1]

        #get the model class:
        try:
            model_class = get_model('api', model_name)
        except ValueError:
            raise CommandError('Could not load model \'%s\'.' %(model_name,))

        #check model field is text:
        try:
            field = model_class._meta.get_field(field_name)
        except model_class.FieldDoesNotExist:
            raise CommandError('Field \'%s\'.\'%s\' is not found!' %(model_name, field_name,))
        if not isinstance(field, TextField):
            raise CommandError('Field \'%s\'.\'%s\' is not a text field!' %(model_name, field_name))

        #setup converter method:
        converter_method = self._markdown_to_html if options['from_markdown'] else self._plain_text_to_html

        #show warning message before saving to objects;
        if not options['print_only']:
            ans = raw_input(
                'WARNING:\n'
                'This is going to convert \'%s\'.\'%s\' field from text to HTML...\n'
                'If it is already converted to HTML, then the data might be corrupted (you can check output strings with --print-only option).\n'
                'Are you sure you want to save to objects [yes/NO]? ' % (
                    model_name, field_name,
                )
            )
            if ans.lower() != 'yes':
                print 'Aborted!'
                return

        #go over all objects and convert their fields to HTML:
        for obj in model_class.objects.all():
            #convert original text/markdown to HTML:
            orig_text = getattr(obj, field_name)
            html = converter_method(orig_text)
            html = html.strip()
            html = sanitize.sanitize_html(html)

            #only print, but do not save:
            if options['print_only']:
                print '---ORIGINAL:\n', orig_text
                print '---HTML\n', html
                key = raw_input('... (press enter or q to quit)')
                if key == 'q':
                    break
                continue

            setattr(obj, field_name, html)
            obj.save()
