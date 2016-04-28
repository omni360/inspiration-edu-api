from django.db import models
from django.utils.timezone import datetime, now as utc_now
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django_counter_field import CounterMixin

from . import managers


class TimestampedModel(CounterMixin, models.Model):
    """
    Abstract base model that keeps track of added/updated timestamps.
    """
    added = models.DateTimeField(db_index=True, auto_now_add=True)
    updated = models.DateTimeField(db_index=True, default=utc_now)

    class Meta(object):
        abstract = True

    def save(self, *args, **kwargs):
        change_updated_field = kwargs.pop('change_updated_field', True)
        if change_updated_field:
            self.updated = change_updated_field if isinstance(change_updated_field, datetime) else utc_now()
            if 'update_fields' in kwargs and 'updated' not in kwargs['update_fields']:
                #Note: do not use .append or += since it changes the original list.
                kwargs['update_fields'] = kwargs['update_fields'] + ['updated']
        super(TimestampedModel, self).save(*args, **kwargs)

    def _change_updated_field_for_parent(self, parent, updated=None):
        updated = updated or utc_now()
        parent.updated = updated
        parent.save(update_fields=['updated'], change_updated_field=updated)
        parent.change_parent_updated_field(updated)

    def change_parent_updated_field(self, updated=None):
        # Use ._change_updated_field_for_parent() method to change updated field for specified parents.
        pass


class DeleteStatusModel(models.Model):
    """
    Abstract base model that flags an object as deleted instead of actually
    deleting it.
    """
    is_deleted = models.BooleanField(default=False, db_index=True)
    objects = managers.DeleteStatusManager()

    class Meta:
        abstract = True

    def delete(self, **kwargs):
        if kwargs.pop('really_delete', False):
            super(DeleteStatusModel, self).delete()
        else:
            self.is_deleted = True
            self.save()


class GenericLinkedModel(models.Model):
    """
    Abstract base model that allows for an object to be linked (foreign-keyed)
    to various models. Useful example: Comments or tags for different types of
    objects.

    Example Usage:
    ==============
    
    from django.contrib.contenttypes.fields import GenericRelation
    ...

    class Comment(GenericLinkedModel):
        text = models.Charfield(max_length=500)
        ...

    class Post(models.Model):
        comments = GenericRelation(Comment)
        ...

    """

    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField(db_index=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        abstract = True
