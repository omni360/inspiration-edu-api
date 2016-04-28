from django.views.generic import TemplateView

from editor_tools.models import BadWord

from guardian_moderation import _has_moderation_permission


class BadWordsSetupView(TemplateView):
    template_name = 'admin/bad_words_setup.html'

    def get_context_data(self, **kwargs):
        context = super(BadWordsSetupView, self).get_context_data(**kwargs)
        context.update({
            'title': 'Bad Words Setup',
            'bad_words_list': getattr(self, 'bad_words_list'),
        })
        return context

    @_has_moderation_permission
    def dispatch(self, request, *args, **kwargs):
        self.bad_words_list = [bad_word for bad_word in BadWord.objects.order_by('text').values_list('text', flat=True)]

        return super(BadWordsSetupView, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        old_bad_words_list = self.bad_words_list

        # Get new bad words list:
        new_bad_words_text = request.POST.get('newBadWordsText', '')
        new_bad_words_list = [new_bad_word.strip().lower() for new_bad_word in new_bad_words_text.splitlines()]

        # Remove old bad words list:
        BadWord.objects.exclude(text__in=new_bad_words_list).delete()

        # Insert new bad words list:
        BadWord.objects.bulk_create([
            BadWord(text=new_bad_word.strip().lower())
            for new_bad_word in set(new_bad_words_list) - set(old_bad_words_list)
            if new_bad_word
        ])

        # Put words to cache and get them:
        self.bad_words_list = BadWord.put_words_to_cache()

        return super(BadWordsSetupView, self).get(request, *args, **kwargs)
