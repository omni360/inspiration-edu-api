from collections import namedtuple

from django.db.models import Prefetch

from rest_framework import serializers
from api.models import LessonState, ProjectState, Project, Lesson, Step
from drafts.serializers import DraftSerializerMixin
from drafts.serializers import DraftListSerializerMixin  # keep DraftListSerializerMixin available in this package


class CheckBeforePublishMixin(object):
    '''
    A serializer mixin that checks whether a list of fields (defined on
    Meta.required_on_publish) is filled in when the publish_mode field is set to "published".
    '''

    def check_before_publish(self, instance, attrs):
        """
        Checks that data is valid before publish.
        It is possible to extend this method for further checking before publish.
        """
        attrs = attrs or {}

        errors = {}
        required_on_publish = getattr(self.Meta, 'required_on_publish', {})
        for field_name, attr_name in required_on_publish.items():
            # Check whether the field is set on instance:
            if not attrs.get(attr_name, getattr(instance, attr_name, None)):
                field_name_chunks = field_name.split('.')
                errors_chunk = errors
                for field_name_chunk in field_name_chunks[:-1]:
                    errors_chunk.setdefault(field_name_chunk, {})
                    errors_chunk = errors_chunk[field_name_chunk]
                errors_chunk[field_name_chunks[-1]] = ['This field is required before publishing']

        return errors


class DynamicFieldsMixin(object):
    """
    A serializer mixin that takes an additional `fields` argument that controls
    which fields should be displayed.
 
    Usage::
 
        class MySerializer(DynamicFieldsMixin, serializers.HyperlinkedModelSerializer):
            class Meta:
                model = MyModel

    From: http://stackoverflow.com/questions/23643204/django-rest-framework-dynamically-return-subset-of-fields
    and https://gist.github.com/dbrgn/4e6fc1fe5922598592d6
    """
    def _prepare_fields(self):
        fields = None
        if self.context.get('request'):
            fields = self.context['request'].QUERY_PARAMS.get('fields')
        if fields:
            fields = fields.split(',')
            # Drop any fields that are not specified in the `fields` argument.
            allowed = set(fields)
            existing = set(self.fields.keys())
            for field_name in existing - allowed:
                self.fields.pop(field_name)

    def to_native(self, obj):
        self._prepare_fields()
        return super(DynamicFieldsMixin, self).to_native(obj)

    def from_native(self, data, files):
        self._prepare_fields()
        return super(DynamicFieldsMixin, self).from_native(data, files)


# A named tuple for the dynamic serializers
DynamicSerializer = namedtuple('DynamicSerializer', ['simple', 'embed'])


class DynamicEmbedMixin(object):
    """
    A serializer mixin that takes an additional `embed` argument, selecting
    which fields should be nested and expanded (embedded).
    """
    def _prepare_embed_fields(self):
        field_to_embed = []

        if self.context.get('request'):
            embed = self.context['request'].QUERY_PARAMS.get('embed')
            if embed:
                embed = embed.split(',')
                field_to_embed = [unicode(field) for field in set(embed)]

        # Add/edit fields on this serializer, based on the embed param.
        if self.Meta.embed:
            for name, serializers in self.Meta.embed.iteritems():
                if type(serializers) is not DynamicSerializer:
                    raise ValueError('embedded field should be a DynamicSerializer instance')
                else:
                    self.fields[name] = serializers.embed if (name in field_to_embed) else serializers.simple

    def to_native(self, obj):
        self._prepare_embed_fields()
        return super(DynamicEmbedMixin, self).to_native(obj)

    def from_native(self, data, files):
        self._prepare_embed_fields()
        return super(DynamicEmbedMixin, self).from_native(data, files)


class ProjectClassroomAuthenticatedMixin(object):

    # enrolled = serializers.SerializerMethodField('get_enrolled_state')
    # state = serializers.SerializerMethodField()

    def _get_user_state(self, obj):
        if getattr(obj, 'user_registration', None) is not None:
            # Get state from the user_registration attribute.
            # If attribute is an empty list, this means that there's no project
            # state for this lesson in the database.
            state = obj.user_registration[0] if obj.user_registration else None
        else:
            # Fetch the project state from the database.
            state = obj.registrations.filter(user=self.context.get('request').user).first()

        return state

    def get_enrolled_state(self, obj):
        """Returns True\False designating whether the user is enrolled or not"""

        # If the object has a user_registration attribute.
        # This attribute is prefetched_related.
        return self._get_user_state(obj) is not None

    def get_state(self, obj):
        """Returns the project state of the current user"""

        # This is the same basic trick as get_enrolled_state. The only
        # difference is that we return the state instead of whether the user
        # is enrolled.

        state = self._get_user_state(obj)
        if not state:
            return None
        field_serializer = self.state_serializer(state)
        field_serializer.parent=self
        field_serializer.field_name='state'
        return field_serializer.data


class ProjectDraftSerializerMixin(DraftSerializerMixin):
    """
    Embeds 'draft' JSON field to serializer that shows the diff fields of the draft object.

    The fields 'draft' and 'origin' are only shown when serializer context['allowed'] list includes them.
    """

    def __init__(self, *args, **kwargs):
        # Setup serializer for draft:
        use_draft_instance = kwargs.get('use_draft_instance', self.use_draft_instance)
        if use_draft_instance:
            # allowed 'origin' field
            context = kwargs.get('context', {})
            allowed = list(context.get('allowed', []))
            if 'origin' not in allowed:
                allowed.append('origin')
            context['allowed'] = tuple(allowed)
            kwargs['context'] = context

        super(ProjectDraftSerializerMixin, self).__init__(*args, **kwargs)

    def get_draft_data(self, origin_obj):
        # Returns draft data with diff from origin:
        if not origin_obj.has_draft:
            return None
        draft_obj = origin_obj.draft_object
        return {
            'id': draft_obj.id,
            'self': self.fields['self'].to_representation(draft_obj),
            'diff': self.get_diff_data(origin_obj, draft_obj),
            'created': draft_obj.added,
            'updated': draft_obj.updated,
        }

    def get_origin_data(self, draft_obj):
        # Returns origin data with diff from draft:
        if not draft_obj.is_draft:
            return None
        origin_obj = draft_obj.draft_origin
        return {
            'id': origin_obj.id,
            'self': self.fields['self'].to_representation(origin_obj),
            'diff': self.get_diff_data(draft_obj, origin_obj),
            'created': origin_obj.added,
            'updated': origin_obj.updated,
        }

    def to_representation(self, instance):
        ret = super(ProjectDraftSerializerMixin, self).to_representation(instance)

        allowed = self.context.get('allowed', [])

        # If 'draft' in context allowed:
        if not instance.is_draft and 'draft' in allowed:
            # Get project object of instance, and request user:
            project_obj = None
            if isinstance(instance, Project):
                project_obj = instance
            elif isinstance(instance, Lesson):
                project_obj = instance.project
            elif isinstance(instance, Step):
                project_obj = instance.lesson.project
            else:
                raise AssertionError('ProgrammingError: \'%s\' is not suitable for %s.' %(self.__class__.__name__, instance._meta.object_name))
            request_user = getattr(self.context.get('request'), 'user', None)

            # If user can not view draft, remove the field before serializing to representation:
            req_hash = self.context.get('request').QUERY_PARAMS.get('hash', None)
            if (
                (project_obj.has_draft and project_obj.draft_object.can_view(request_user, view_hash=req_hash)) or
                (not project_obj.has_draft and (project_obj.is_editor(request_user) or project_obj.is_viewer(request_user)))
            ):
                ret['draft'] = self.get_draft_data(instance)

        # If 'origin' in context allowed:
        if instance.is_draft and 'origin' in allowed:
            ret['origin'] = self.get_origin_data(instance)

        return ret


class MirrorFieldsMixin(object):
    '''
    A mixin to mirror fields.
    Usage: set mirror_fields in Meta class to be a list of (field_source, field_target) tuples.
    This mixin adds the target mirrors to the native output, and removes the target from the input data.
    '''
    def to_native(self, obj):
        mirror_fields = getattr(self.Meta, 'mirror_fields', [])
        ret = super(MirrorFieldsMixin, self).to_native(obj)
        if ret:
            for mirror_field_source, mirror_field_target in mirror_fields:
                if mirror_field_source in ret:
                    ret[mirror_field_target] = ret[mirror_field_source]
        return ret

    def from_native(self, data, files):
        mirror_fields = getattr(self.Meta, 'mirror_fields', [])
        if data:
            for mirror_field_source, mirror_field_target in mirror_fields:
                if mirror_field_target in data:
                    del data[mirror_field_target]
        return super(MirrorFieldsMixin, self).from_native(data, files)
