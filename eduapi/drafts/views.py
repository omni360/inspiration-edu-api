from django.shortcuts import render
from rest_framework import exceptions

class DraftViewMixin(object):
    """
    Mixin used for views that use draft object.
    The view model object is the original object. Make serializer to handle the draft crate/update instead of the original object.
    """

    def get_object(self):
        obj = super(DraftViewMixin, self).get_object()

        # If request method is not for creating draft:
        if self.request.method not in ['POST', 'PUT', 'PATCH']:
            # Check that object has draft:
            if not obj.has_draft:
                raise exceptions.NotFound

        return obj

    def get_serializer(self, *args, **kwargs):
        kwargs['use_draft_instance'] = True
        serializer = super(DraftViewMixin, self).get_serializer(*args, **kwargs)
        return serializer

    def perform_destroy(self, instance):
        instance.draft_discard()

    def post(self, request, *args, **kwargs):
        # POST redirects to .update() method - handle both create and update in .perform_update.
        return self.update(request, *args, **kwargs)
