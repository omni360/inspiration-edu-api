from django.db import models
from django.db.models.query import QuerySet


class DeleteStatusManager(models.Manager):
    """
    Manager that marks objects as deleted instead of actually deleting them.

    Expects to be used with a model with an ``is_deleted`` boolean field.

    Hides deleted objects from ``all()``, and in addition gives an easy way
    to filter them in/out (``deleted()``/``active()``). Also overrides
    ``delete()`` to mark deleted in bulk.
    """

    def get_queryset(self):
        return DeleteStatusQuerySet(self.model, using=self._db).active()

    def get_all_queryset(self):
        return DeleteStatusQuerySet(self.model, using=self._db).active_and_deleted()

    def active(self):
        """
        Return only objects that haven't been deleted.
        """
        return self.get_queryset().active()

    def deleted(self):
        """
        Return only objects that have been deleted.
        """
        return self.get_all_queryset().deleted()

    def active_and_deleted(self):
        """
        Returns both active and deleted objects
        """
        return self.get_all_queryset().active_and_deleted()


class DeleteStatusQuerySet(QuerySet):
    """
    QuerySet to manage objects with ``is_deleted`` flags.

    See DeleteStatusManager for more details.
    """
    def active(self):
        """
        Return only objects that haven't been deleted.
        """
        return self.filter(is_deleted=False)

    def deleted(self):
        """
        Return only objects that have been deleted.
        """
        return self.filter(is_deleted=True)

    def active_and_deleted(self):
        """
        Returns both active and deleted objects
        """
        return self.all()

    def delete(self, **kwargs):
        """
        Mark records in the current QuerySet as deleted.
        """
        if kwargs.pop('really_delete', False):
            super(DeleteStatusQuerySet, self).delete()
        else:
            self.update(is_deleted=True)

class DeleteStatusWithDraftManager(DeleteStatusManager):
    """
    DeleteStatusManager for objects with ``draft_origin``.
    """
    def get_queryset(self):
        return DeleteStatusWithDraftQuerySet(self.model, using=self._db).active()

    def get_all_queryset(self):
        return DeleteStatusWithDraftQuerySet(self.model, using=self._db).active_and_deleted()

    def origins(self):
        return self.get_queryset().origins()

    def drafts(self):
        return self.get_queryset().drafts()


class DeleteStatusWithDraftQuerySet(DeleteStatusQuerySet):
    """
    DeleteStatusQuerySet to manage objects with ``draft_origin``.
    """
    def origins(self):
        """
        Return only objects that are not drafts.
        """
        return self.filter(draft_origin__isnull=True)

    def drafts(self):
        """
        Return only objects that are drafts.
        """
        return self.filter(draft_origin__isnull=False)

    def origins_and_drafts(self):
        """
        Return both origins and drafts objects.
        """
        return self.all()

class DeleteStatusWithDraftOriginsManager(DeleteStatusWithDraftManager):
    """
    DeleteStatusWithDraftManager for objects with draft.
    Only difference is that default queryset is active() and origins().
    """
    def get_queryset(self):
        return super(DeleteStatusWithDraftOriginsManager, self).get_queryset().origins()
