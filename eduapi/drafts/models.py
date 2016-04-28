from django.db import models

class ChangeableDraftModel(models.Model):
    """
    Abstract base model that allows to create a draft object replicated from original self object and apply
    set of specific fields (draft_writable_data_fields).
    It is optional to define additional fields in the draft that might be updated (through .save() method), but they
    will not be applied to original object (draft_writable_meta_fields).
    If the object is draft and object model inherits abstract DeleteStatusModel, then draft is_deleted will be True,
    so it will be invisible in default objects queryset. (If not, then make sure to hide drafts objects in queryset,
    e.g: .filter(draft_origin__isnull=True) - will filter out drafts objects).
    """
    draft_origin = models.OneToOneField('self', related_name='draft_object', null=True, default=None)

    draft_writable_data_fields = []
    draft_writable_meta_fields = []
    draft_create_fields = []

    class Meta:
        abstract = True

    @property
    def is_draft(self):
        """Whether this object is draft."""
        return self.draft_origin is not None

    @property
    def has_draft(self):
        """Whether this object has own draft."""
        return hasattr(self, 'draft_object')

    def save(self, *args, **kwargs):
        # If object is draft, then update only allowed fields:
        if self.is_draft and self.pk:
            draft_allowed_update_fields = list(self.draft_writable_data_fields) + list(self.draft_writable_meta_fields)
            update_fields = kwargs.get('update_fields', draft_allowed_update_fields)
            update_fields = [f for f in update_fields if f in draft_allowed_update_fields]
            kwargs['update_fields'] = update_fields
        return super(ChangeableDraftModel, self).save(*args, **kwargs)

    def draft_get(self):
        """Returns draft object if draft was created or None."""
        if self.is_draft:
            return self
        if self.has_draft:
            return self.draft_object
        return None

    def draft_get_or_create(self, draft_create_fields=None):
        """
        Gets draft object or creates a new draft object for this self origin object.
        Returns tuple of (draft_object, created).
        """
        # draft object can not have a draft:
        if self.is_draft:
            return self, False

        # if object already has draft:
        if self.has_draft:
            return self.draft_object, False

        # create a fresh new draft object:
        draft_obj = self._meta.model.objects.get(pk=self.pk)
        draft_allowed_create_fields = list(self.draft_writable_data_fields) + list(self.draft_writable_meta_fields) + list(self.draft_create_fields)
        for draft_create_field_key, draft_create_field_value in draft_create_fields.items():
            if draft_create_field_key in draft_allowed_create_fields:
                setattr(draft_obj, draft_create_field_key, draft_create_field_value)
        draft_obj.pk = None
        draft_obj.draft_origin = self
        draft_obj.save()
        return draft_obj, True

    def draft_discard(self, draft_delete_kwargs=None):
        """
        Discards the draft object (really deletes it from database).
        """
        # get draft object:
        draft_object = self.draft_get()
        if not draft_object or draft_object.pk is None:  #discarded draft object has no pk
            return False

        # really delete draft object:
        draft_delete_kwargs = draft_delete_kwargs or {}
        draft_object.delete(**draft_delete_kwargs)
        #NOTE: Following line throws exception, but solved in v1.9.
        # draft_object.draft_origin.draft_object = None  #remove draft object from origin cache
        return True

    def draft_apply(self, only_when_changed=True, deep=True):
        """
        If this object is draft, then apply draft_copy_fields to origin object and save.
        You may extend this apply draft method for complex models (e.g model that has related objects drafts).
        Draft is not deleted after apply, so, if needed, make sure to discard the draft after applying.
        If only_when_changed is True, then draft origin is saved only when it is changed.
        If deep is True, then apply draft recursively for any related object that is also draft.
        """
        # get draft object:
        draft_object = self.draft_get()
        if not draft_object:
            return False

        # copy draft apply fields from draft object to origin, and save origin:
        diff_fields = draft_object.draft_diff_fields() if only_when_changed else None
        if diff_fields or not only_when_changed:
            # copy draft apply fields from draft object to origin:
            for f in draft_object.draft_writable_data_fields:
                setattr(draft_object.draft_origin, f, getattr(draft_object, f))
            draft_object.draft_origin.save(update_fields=self.draft_writable_data_fields)

        # recursively apply draft of related objects that are also drafts:
        if deep:
            # go over all related objects fields that are instance of ChangeableDraftModel:
            related_draft_objects_fields = [
                f for f in self._meta.get_fields()
                if (
                    (f.one_to_one or f.one_to_many) and f.auto_created and  # related object field
                    issubclass(f.related_model, ChangeableDraftModel) and  # uses drafts
                    f.name != 'draft_object'  # exclude draft_object related object field
                )
            ]
            for rel_field in related_draft_objects_fields:
                # go over all related objects instances that are drafts:
                related_draft_objects = rel_field.related_model.objects.filter(**{
                    rel_field.field.name: draft_object,
                    'draft_origin__isnull': False,
                })
                for related_draft_obj in related_draft_objects:
                    related_draft_obj.draft_apply(only_when_changed=only_when_changed, deep=deep)

        return True

    def draft_diff_fields(self):
        """Returns list of changed fields in draft compared to origin, or None if no draft."""
        # get draft object:
        draft_object = self.draft_get()
        if not draft_object:
            return None

        # get changed diff fields:
        diff_fields = []
        for f in draft_object.draft_writable_data_fields:
            if getattr(draft_object.draft_origin, f) != getattr(draft_object, f):
                diff_fields.append(f)
        return diff_fields
