from django.db.models import QuerySet


class DraftSerializerMixin(object):
    """
    Mixin for serializer of models using ChangeableDraftModel.
    Allows to set use_draft_instance which makes use of the serializer to update the draft object instead of the
    object itself.
    When use_draft_instance, the mixin makes all the fields that could not be updated in the draft as read-only,
    and validates and saves the data using the draft object.
    This serializer handles sub-serializers of itself, so fields in the sub-serializers that are not editable for
    draft are marked read-only. (See example of teacherInfo serializer field in ProjectSerializer).
    """
    use_draft_instance = False

    def __init__(self, *args, **kwargs):
        self.use_draft_instance = kwargs.pop('use_draft_instance', self.use_draft_instance)

        # Setup serializer for draft:
        if self.use_draft_instance:
            # get instance from args/kwargs if exists and use it as origin
            self.draft_origin_instance = args[0] if len(args) > 0 else kwargs.pop('instance', None)
            new_draft_instance = None

            # if got origin instance and origin is used as single:
            if self.draft_origin_instance is not None and not hasattr(self.draft_origin_instance, '__iter__'):
                # make sure that if got draft_origin_instance then it must be origin
                assert not self.draft_origin_instance.is_draft, (
                    'Draft view must supply the serializer an instance of the origin object, and not the draft object.'
                )
                # make new draft instance to be the draft object:
                new_draft_instance = self.draft_origin_instance.draft_get()

                # set instance to draft object (in case origin instance is not given, then init without instance object)
                args = list(args)
                if len(args) == 0:
                    args.append(None)
                args[0] = new_draft_instance

            super(DraftSerializerMixin, self).__init__(*args, **kwargs)

            self.partial = True  # draft always uses partial update
            self._make_not_editable_draft_fields_read_only()

        # Setup default
        else:
            super(DraftSerializerMixin, self).__init__(*args, **kwargs)

    @classmethod
    def many_init(cls, *args, **kwargs):
        use_draft_instance = kwargs.get('use_draft_instance', cls.use_draft_instance)

        # Setup list serializer for draft:
        if use_draft_instance:
            # Note: Since with list serializer for draft creation of new draft is not allowed [unlike serializer of
            #       single draft], we can (and should) pass the list serializer a queryset of the drafts.
            # ***** Use the following asserts for debugging only:
            # drafts_list = args[0] if len(args) > 0 else kwargs.pop('instance', None)
            # if isinstance(drafts_list, QuerySet):
            #     assert drafts_list.filter(draft_origin__isnull=False).count() == drafts_list.count(), (
            #         'Draft list view must supply the serializer a queryset of the drafts objects only, and not the origins objects.'
            #     )
            # elif isinstance(drafts_list, list):
            #     for draft_obj in drafts_list:
            #         assert draft_obj.is_draft, (
            #             'Draft list view must supply the serializer a queryset of the drafts objects only, and not the origins objects.'
            #         )
            # ***** Until here.

            # draft always uses partial update
            kwargs['partial'] = True

        return super(DraftSerializerMixin, cls).many_init(*args, **kwargs)

    def _make_not_editable_draft_fields_read_only(self):
        draft_editable_fields = list(self.Meta.model.draft_writable_data_fields) + list(self.Meta.model.draft_writable_meta_fields)
        for field_name, field in self.fields.items():
            # Field is sub-serializer that allows draft and editable - make its sub not editable draft fields read only:
            if isinstance(field, DraftSerializerMixin) and not field.read_only:
                field._make_not_editable_draft_fields_read_only()
            elif not field.read_only and field.source not in draft_editable_fields:
                field.read_only = True

    def get_diff_data(self, obj, against_obj):
        # Get the diff fields, and make dict of diff fields with the values against_obj:
        diff_fields = obj.draft_diff_fields()
        diff_data = {}
        for field_name, field in self.fields.items():
            # Field is sub-serializer that allows draft - get its sub diff data:
            if isinstance(field, DraftSerializerMixin):
                # If source is '*' then use the obj, otherwise get the attribute value:
                field_obj = obj if field.source == '*' else (obj.get(field.source) if isinstance(obj, dict) else getattr(obj, field.source))
                field_against_obj = against_obj if field.source == '*' else (against_obj.get(field.source) if isinstance(against_obj, dict) else getattr(against_obj, field.source))
                # Get the sub diff data and put it in diff data if not empty:
                field_diff_data = field.get_diff_data(field_obj, field_against_obj)
                if field_diff_data:
                    diff_data[field_name] = field_diff_data
            # Regular field - check source:
            elif field.source in diff_fields:
                # If source is '*' then use the obj, otherwise get the attribute value:
                value = against_obj if field.source == '*' else (against_obj.get(field.source) if isinstance(against_obj, dict) else getattr(against_obj, field.source))
                diff_data[field_name] = field.to_representation(value) if value is not None else None
        return diff_data

    def create(self, validated_data):
        # If use draft, then create draft instance from the origin instance and call .update():
        if self.use_draft_instance:
            self.instance, _ = self.draft_origin_instance.draft_get_or_create()
            return self.update(self.instance, validated_data)

        # Otherwise, use default .create():
        return super(DraftSerializerMixin, self).create(validated_data)


class DraftListSerializerMixin(object):
    use_draft_instance = False

    def __init__(self, *args, **kwargs):
        self.use_draft_instance = kwargs.pop('use_draft_instance', self.use_draft_instance)
        super(DraftListSerializerMixin, self).__init__(*args, **kwargs)
