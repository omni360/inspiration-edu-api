from django.db import models
from django.core.cache import cache


class BadWord(models.Model):
    text = models.TextField(max_length=50, unique=True)

    def save(self, *args, **kwargs):
        save_result = super(BadWord, self).save(*args, **kwargs)
        self.put_words_to_cache()
        return save_result

    @classmethod
    def put_words_to_cache(cls):
        bad_words_list = [bad_word.strip().lower() for bad_word in cls.objects.all().values_list('text', flat=True)]
        cache.set('bad_words_list', bad_words_list, None)
        return bad_words_list

    @classmethod
    def get_words_from_cache(cls):
        bad_words_list = cache.get('bad_words_list', None)
        if bad_words_list is None:
            bad_words_list = cls.put_words_to_cache()
        return bad_words_list
