import json
import re

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from notifications.models import Notification

from rest_framework import serializers
from rest_framework.reverse import reverse
from rest_framework.serializers import raise_errors_on_nested_writes
from rest_framework_bulk import BulkSerializerMixin, BulkListSerializer

from api.serializers.common import DynamicFieldsModelSerializer
from django.db.models import Prefetch
from django.contrib.auth import get_user_model
from api.tasks import fix_lesson_counter
from utils_app.counter import ExtendQuerySetWithSubRelated

from .fields import (
    JSONField,
    URLField,
    StepHyperlinkedIdentityField,
    InlineListRelatedField,
    UserStateIdentityField,
    ViewedStepsRelatedField,
    LessonHyperlinkedField,
    LessonHyperlinkedIdentityField,
    OrderedSerializerRelatedField,
    HtmlField,
)
from .validators import (
    InlineVideoJSONValidator,
    InlineTeacherFileJSONValidator,
    InstructionJSONValidator,
    InstructablesJSONValidator,
)
from .mixins import (
    DynamicFieldsMixin,
    CheckBeforePublishMixin,
    ProjectDraftSerializerMixin,
    DraftListSerializerMixin,
)
from .users import (
    UserSerializer,
)

from ..models import (
    Classroom,
    Project,
    Lesson,
    Step,
    ProjectState,
    LessonState,
    StepState,
    ViewInvite
)

from marketplace.models import Purchase


#region Step Serializers
class StepListSerializer(BulkListSerializer, DraftListSerializerMixin, serializers.ListSerializer):
    def update(self, instance, validated_data):
        #if not POST or PUT (PUT-as-create, POST-as-update), use default BulkListSerializer.update():
        # Note: For draft list, the default bulk update is suitable, since it validates all ids exist.
        if getattr(self.context.get('request'), 'method', None) not in ['POST', 'PUT']:
            # #validate that each item has identifier field:
            # errors = []
            # for item_data in validated_data:
            #     if item_data['id'] is None or item_data['id'] is serializers.empty:
            #         errors.append({
            #             'id': ['Must specify item identifier to update.']
            #         })
            #     else:
            #         errors.append({})
            # if any(errors):
            #     raise serializers.ValidationError(errors)
            return super(StepListSerializer, self).update(instance, validated_data)

        # Maps for id->instance and id->data item.
        steps_mapping = {step.id: step for step in instance}

        # Perform creations and updates.
        ret = []
        for step_data in validated_data:
            step = steps_mapping.get(step_data.get('id'))
            if step is None:
                step_data.pop('id', None)  #TODO: validate that when 'id' is used, the item exists in the instance
                ret.append(self.child.create(step_data))
            else:
                ret.append(self.child.update(step, step_data))

        return ret


class StepSerializer(DynamicFieldsMixin, ProjectDraftSerializerMixin, DynamicFieldsModelSerializer, BulkSerializerMixin, serializers.ModelSerializer):
    instructions = serializers.ListField(allow_null=True,
                                         required=False,
                                         source='instructions_list',
                                         child=JSONField(validators=(InstructionJSONValidator(),))
                                         )
    description = HtmlField(required=False, allow_blank=True,
                            sanitize_options={
                                'tags': HtmlField.defaults_sanitize_options.get('tags', []) + ['img',]
                            })
    image = URLField(label='Image', required=False, allow_blank=True, allow_null=True, help_text='A URL to an image for the step')
    lesson = LessonHyperlinkedField(read_only=True, required=False, view_name='api:project-lesson-detail')
    lessonId = serializers.PrimaryKeyRelatedField(source='lesson', read_only=True)
    self = StepHyperlinkedIdentityField(view_name='api:project-lesson-step-detail', draft_view_name='api:project-lesson-step-draft-detail')
    applicationBlob = JSONField(
        source='application_blob',
        label='Application Blob',
        required=False,
        style={'input_type': 'textarea'},
        help_text='A JSON field that stores application specific data',
    )
    order = serializers.IntegerField(min_value=0, allow_null=True, required=False)

    class Meta:
        model = Step
        lookup_field = 'order'
        fields = (
            'id',
            'self',
            'order',
            'title',
            'description',
            'image',
            'applicationBlob',
            'lesson',
            'lessonId',
            'instructions',
        )
        # We explicitly set validators because otherwise DRF uses the
        # UniqueTogetherValidator based on the fact that there's a 
        # unique_together in the model. This is a problem because then DRF 
        # expects 'lesson' to be a non-read-only field. See: 
        # http://www.django-rest-framework.org/api-guide/validators/#uniquetogethervalidator
        # Setting validators explicitly overrides the defaults that are taken form the model.
        validators = []
        list_serializer_class = StepListSerializer

    def validate(self, attrs):
        attrs = super(StepSerializer, self).validate(attrs)

        # Remove lesson_id from validated_data if using draft:
        if self.use_draft_instance:
            attrs.pop('lesson_id', None)

        return attrs


class StepListSerializerField(BulkListSerializer, serializers.ListSerializer):
    """
    Helper serializer field for steps list nested field in LessonSerializer.
    """

    def __init__(self, *args, **kwargs):
        child = StepSerializer(*args, **kwargs)
        child.fields['id'].read_only = False
        kwargs['child'] = child
        kwargs.pop('use_draft_instance', None)
        super(StepListSerializerField, self).__init__(*args, **kwargs)

    def update(self, instance, validated_data):
        # Maps for id->instance item.
        steps_mapping = {step.id: step for step in instance}

        # Perform creations and updates.
        ret = []
        for step_data in validated_data:
            step = steps_mapping.get(step_data.get('id'))
            if step is None:
                step_data.pop('id', None)  #TODO: validate that when 'id' is used, the item exists in the instance
                ret.append(self.child.create(step_data))
            else:
                ret.append(self.child.update(step, step_data))

        # Perform deletions:
        ids_to_delete = list(set(steps_mapping.keys()) - set([x.id for x in ret]))
        for step_id in ids_to_delete:
            step_to_delete = steps_mapping.get(step_id)
            if step_to_delete:
                step_to_delete.delete()

        return ret
#endregion Step Serializers


class LessonStateSerializer(serializers.ModelSerializer):
    """
    Serializes a lesson state for the current user.
    """
    userId = serializers.ReadOnlyField(source='project_state.user_id')
    user = serializers.HyperlinkedRelatedField(source='project_state.user', view_name='api:user-detail', read_only=True)

    id = serializers.PrimaryKeyRelatedField(source='lesson', read_only=True)
    lesson = LessonHyperlinkedField(view_name='api:project-lesson-detail', read_only=True)
    title = serializers.ReadOnlyField(source='lesson.title')
    image = serializers.ReadOnlyField(source='lesson.image')
    viewedSteps = serializers.PrimaryKeyRelatedField(source='viewed_steps', many=True, read_only=False, required=False, queryset=Step.objects.all())
    enrolltime = serializers.ReadOnlyField(source='added')
    isCompleted = serializers.BooleanField(source='is_completed', default=False, required=False)

    # The self URL should point to the /user/:id/state/ because this API can
    # be accessed both by /me/ and by the user's guardians.
    self = UserStateIdentityField(
        lookup_field='lesson_id',
        pk_url_kwarg='lesson_pk',
        view_name='api:user-project-lesson-state-detail'
    )
    updated = serializers.DateTimeField(read_only=True)
    extra   = JSONField(
        label='User Blob',
        required=False,
        allow_null=True,
        help_text='A JSON field that stores user specific data',
    )

    numberOfLessonSteps = serializers.ReadOnlyField(source='lesson.steps_count')

    class Meta:
        model = LessonState
        fields = (
            'id',
            'lesson',
            'userId',
            'user',
            'title',
            'image',
            'self',
            'enrolltime',
            'viewedSteps',
            'isCompleted',
            'numberOfLessonSteps',
            'extra',
            'updated',
        )

    def __init__(self, *args, **kwargs):
        super(LessonStateSerializer, self).__init__(*args, **kwargs)

        context = kwargs.get('context', {})

        #if 'lesson' is in context, then make it "id" default, otherwise make "id" field required:
        lesson = context.get('lesson')
        if lesson:
            self.fields['id'].default = lesson
        else:
            self.fields['id'].read_only = False
            self.fields['id'].required = True
            self.fields['id'].queryset = Lesson.objects.all()

    def validate_viewedSteps(self, value):
        #remove duplicates:
        return list(set(value))

    def validate(self, attrs):
        attrs = super(LessonStateSerializer, self).validate(attrs)

        #validate that all steps are in lesson:
        viewed_steps = attrs.get('viewed_steps', [])
        if viewed_steps:
            viewed_steps_ids = [x.id for x in viewed_steps]
            lesson_viewed_steps_ids = attrs['lesson'].steps.filter(pk__in=viewed_steps_ids).values_list('id', flat=True)
            invalid_viewed_steps_ids = (set(viewed_steps_ids) - set(lesson_viewed_steps_ids))
            if invalid_viewed_steps_ids:
                raise serializers.ValidationError({
                    'viewedSteps': ['All viewed steps must be steps of the lesson.']
                })

        return attrs

    def _save_viewed_steps_list(self, instance, viewed_steps_list):
        #if None, do nothing:
        if viewed_steps_list is None:
            return

        #create new viewed steps states:
        for viewed_step in viewed_steps_list:
            #Note: (lesson_state, step) is unique.
            step_state, _ = StepState.objects.get_or_create(
                lesson_state=instance,
                step=viewed_step
            )

        #delete existing viewed step states that are not in the viewed steps list:
        for old_step in StepState.objects.filter(lesson_state=instance).exclude(step__in=viewed_steps_list):
            old_step.delete()

        #remove prefetched cache:
        getattr(instance, '_prefetched_objects_cache', {}).pop('viewed_steps', None)

        #since this might change the 'is_completed' of the lesson state,
        #reload the lesson state and set is_completed of the instance:
        reloaded_instance = LessonState.objects.get(pk=instance.pk)
        instance.is_completed = reloaded_instance.is_completed

    def update(self, instance, validated_data):
        viewed_steps_list = validated_data.pop('viewed_steps', None)
        instance = super(LessonStateSerializer, self).update(instance, validated_data)
        self._save_viewed_steps_list(instance, viewed_steps_list)
        return instance

    def create(self, validated_data):
        #create project state if not exist:
        #Note: (project, user) is unique.
        validated_data['project_state'], _ = ProjectState.objects.get_or_create(
            project_id=validated_data['lesson'].project_id,
            user=self.context['request'].user
        )

        viewed_steps_list = validated_data.pop('viewed_steps', None)
        instance = super(LessonStateSerializer, self).create(validated_data)
        self._save_viewed_steps_list(instance, viewed_steps_list)
        return instance


#region Lesson Serializers
class LessonListSerializer(BulkListSerializer, DraftListSerializerMixin, serializers.ListSerializer):
    def update(self, instance, validated_data):
        """
        Currently we are not using update, as the instructions are not passed by ID, but instead are handled by order
        """
        #if not POST or PUT (PUT-as-create, POST-as-update), use default BulkListSerializer.update():
        # Note: For draft list, the default bulk update is suitable, since it validates all ids exist.
        if getattr(self.context.get('request'), 'method', None) not in ['POST', 'PUT']:
            # #validate that each item has identifier field:
            # errors = []
            # for item_data in validated_data:
            #     if item_data['id'] is None or item_data['id'] is serializers.empty:
            #         errors.append({
            #             'id': ['Must specify item identifier to update.']
            #         })
            #     else:
            #         errors.append({})
            # if any(errors):
            #     raise serializers.ValidationError(errors)
            return super(LessonListSerializer, self).update(instance, validated_data)

        # Maps for id->instance and id->data item.
        lesson_mapping = {lesson.id: lesson for lesson in instance}

        # Perform creations and updates.
        ret = []
        # Prevent recalculation of lesson counters in project
        cache.set('fix_message_set_project_%s' % self.context.get('view').kwargs.get('project_pk'), True, timeout=5)
        for lesson_data in validated_data:
            lesson = lesson_mapping.get(lesson_data.get('id'))
            if lesson is None:
                lesson_data.pop('id', None)  #TODO: validate that when 'id' is used, the item exists in the instance
                ret.append(self.child.create(lesson_data))
            else:
                ret.append(self.child.update(lesson, lesson_data))

        return ret


class LessonSerializer(BulkSerializerMixin, CheckBeforePublishMixin, ProjectDraftSerializerMixin, DynamicFieldsModelSerializer):
    self = LessonHyperlinkedIdentityField(view_name='api:project-lesson-detail', draft_view_name='api:project-lesson-draft-detail')

    application = serializers.ChoiceField(choices=Lesson.ENABLED_APPLICATIONS)

    applicationBlob = JSONField(
        source='application_blob',
        label='Application Blob',
        required=False,
        style={'input_type': 'textarea'},
        help_text='A JSON field that stores application specific data',
    )

    publishMode = serializers.ReadOnlyField(source='publish_mode')

    numberOfStudents = serializers.IntegerField(source='students_count', read_only=True)

    added = serializers.DateTimeField(read_only=True)
    updated = serializers.DateTimeField(read_only=True)

    project = serializers.HyperlinkedRelatedField(view_name='api:project-detail', read_only=True)
    projectId = serializers.PrimaryKeyRelatedField(source='project', read_only=True)
    order = serializers.IntegerField(min_value=0, allow_null=True, required=False)
    numberOfSteps = serializers.IntegerField(source='steps_count', read_only=True)

    #removable fields
    steps = StepListSerializerField(required=False)
    state = serializers.SerializerMethodField()
    stepsIds = serializers.PrimaryKeyRelatedField(source='steps', read_only=True, many=True, required=False)

    class Meta:
        model = Lesson
        fields = (
            'id',
            'self',
            'title',
            'duration',
            'application',
            'applicationBlob',

            'project',
            'projectId',
            'order',

            'publishMode',

            'numberOfSteps',
            'numberOfStudents',

            'added',
            'updated',

            # removable fields
            'steps',
            'state',
            'stepsIds',
        )
        validators = []
        dropfields = (
            'steps',
            'stepsIds',
            'state',
        )
        list_serializer_class = LessonListSerializer
        required_on_publish = {
            'duration': 'duration',
        }

    def __init__(self, *args, **kwargs):
        super(LessonSerializer, self).__init__(*args, **kwargs)

        #if embed 'steps' and 'draft'/'origin', then allow 'draft' field for steps list:
        if 'steps' in self.fields:
            context = kwargs.get('context', {})
            allowed = context.get('allowed', [])
            embed_related_kwargs = {
                'use_draft_instance': self.use_draft_instance,
            }
            if 'draft' in allowed:
                embed_related_kwargs['context'] = {'allowed': ['draft']}
            if 'origin' in allowed:
                embed_related_kwargs['context'] = {'allowed': ['origin']}
            self.fields['steps'] = StepListSerializerField(required=False, **embed_related_kwargs)

    def check_before_publish(self, instance, attrs):
        # Regular check instance before publish:
        errors = super(LessonSerializer, self).check_before_publish(instance, attrs)

        # validate other lesson stuff before publish:
        application = attrs.get('application', getattr(instance, 'application', None))
        if application == settings.LESSON_APPS['Video']['db_name']:
            application_blob = attrs.get('application_blob', getattr(instance, 'application_blob', {}))
            video_blob = application_blob.get('video', None)
            if not video_blob:
                errors['applicationBlob'] = ['A video must be set before publishing']
        elif application == settings.LESSON_APPS['Circuits']['db_name']:
            application_blob = attrs.get('application_blob', getattr(instance, 'application_blob', {}))
            start_circuit_id = application_blob.get('startCircuitId', None)
            if not start_circuit_id:
                errors['applicationBlob'] = ['A 123D-Circuits ID must be set before publishing']
        elif application == settings.LESSON_APPS['Instructables']['db_name']:
            application_blob = attrs.get('application_blob', getattr(instance, 'application_blob', {}))
            instructables_blob = application_blob.get('instructables', None)
            if not instructables_blob:
                errors['applicationBlob'] = ['Instructables must be set before publishing']
        if application not in Lesson.STEPLESS_APPS:
            #validate lesson has steps:
            if not instance.steps.exists():
                errors['stepsIds'] = ['Lesson must have steps before publishing']

        return errors

    def to_representation(self, instance):
        # Remove serializer fields for view if request user does not have view permission:
        serializer_fields_for_view = ['applicationBlob', 'steps', 'stepsIds']
        if next((x for x in self.fields.keys() if x in serializer_fields_for_view), None) is not None:
            # If the user does not have view permissions,
            req_hash = self.context.get('request').QUERY_PARAMS.get('hash', None)
            if not instance.project.can_view(self.context['request'].user, view_hash=req_hash):
                # Drop the application blob.
                self.fields.pop('applicationBlob', None)
                self.fields.pop('steps', None)
                self.fields.pop('stepsIds', None)

        return super(LessonSerializer, self).to_representation(instance)

    def get_state(self, obj):
        """Returns the lesson state of the current user"""
        #see documentation at ProjectClassroomAuthenticatedMixin.

        if getattr(obj, 'user_registration', None) is not None:
            state = obj.user_registration[0] if obj.user_registration else None
        else:
            state = obj.registrations.filter(project_state__user=self.context.get('request').user).first()

        if not state:
            return None
        field_serializer = LessonStateSerializer(instance=state, context={'request': self.context['request']})
        return field_serializer.data

    def _validate_attrs_with_instance(self, attrs, instance=None):
        """
        This method is used to validate the data with its corresponding instance.

        Technical Note:
            When using ListSerializer, it validates each item in the data list within the child serializer.
            Surprisingly, it seems that self.instance of the child serializer is the queryset list, and not the
            particular instance.
            Therefore, this workaround is used in .create() and .update() methods of the serializer to validate the
            attributes with that particular corresponding instance.
        """

        # Remove project_id from validated_data if using draft:
        if self.use_draft_instance:
            attrs.pop('project_id', None)

        # Validate by lesson application type.
        app = attrs.get('application') or getattr(instance, 'application', None)
        app_blob = attrs.get('application_blob')
        errors = {}

        # Video Lesson:
        if app_blob and app == settings.LESSON_APPS['Video']['db_name']:
            #validate 'video' field in application_blob:
            video_blob = app_blob.get('video')
            if video_blob:
                video_json_validator = InlineVideoJSONValidator(
                    allowed_vendors=['youtube'],
                    vendor_id_validators={
                        'youtube': lambda x: re.compile(r'^[\w\-]{11}$').match(x),
                    },
                )
                try:
                    video_json_validator(video_blob)
                except ValidationError as err:
                    errors['applicationBlob'] = err.messages
            #sanitize 'description' as html field in application_blob:
            description_blob = app_blob.get('description')
            if description_blob:
                app_blob['description'] = HtmlField().to_internal_value(description_blob)
        # Circuits Lesson:
        if app_blob and app == settings.LESSON_APPS['Circuits']['db_name']:
            #validate 'startCircuitId' in application blob:
            start_circuit_id = app_blob.get('startCircuitId', None) if app_blob else None
            if start_circuit_id:
                try:
                    int(start_circuit_id)
                except ValueError:
                    errors['applicationBlob'] = '\'startCircuitId\' must be an integer.'
        # Instructables Lesson:
        if app_blob and app == settings.LESSON_APPS['Instructables']['db_name']:
            #validate 'instructables' field in application_blob:
            instructables_blob = app_blob.get('instructables')
            if instructables_blob:
                instructables_json_validator = InstructablesJSONValidator()
                try:
                    instructables_json_validator(instructables_blob)
                except ValidationError as err:
                    errors['applicationBlob'] = err.messages

        # If errors, then raise exception:
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def _save_steps_list(self, instance, steps_data):
        #if None, do nothing:
        if steps_data is None:
            return

        #refer each step lesson to the lesson instance:
        for step_data in steps_data:
            step_data['lesson'] = instance
        #step list serializer field updates existing, creates new, deletes missing:
        steps_list = self.fields['steps'].update(instance.steps.all(), steps_data)
        #manually update instance steps count (not saved to db):
        instance.steps_count = len(steps_list)

        #remove prefetch cache:
        getattr(instance, '_prefetched_objects_cache', {}).pop('steps', None)

    def create(self, validated_data):
        validated_data = self._validate_attrs_with_instance(validated_data)
        steps_data = validated_data.pop('steps', None)
        instance = super(LessonSerializer, self).create(validated_data)
        self._save_steps_list(instance, steps_data)

        # set mark if many lessons are updated for same project in short time period
        # if there are - check counter in a few minutes
        if cache.get('project_%s' % instance.project_id) and not cache.get('fix_message_set_project_%s' % instance.project_id):
            fix_lesson_counter.apply_async(args=[instance.project_id,], countdown=5)
            cache.set('fix_message_set_project_%s' % instance.project_id, True, timeout=5)
        else:
            cache.set('project_%s' % instance.project_id, True, timeout=5)
        return instance

    def update(self, instance, validated_data):
        validated_data = self._validate_attrs_with_instance(validated_data, instance)
        steps_data = validated_data.pop('steps', None)
        instance = super(LessonSerializer, self).update(instance, validated_data)
        self._save_steps_list(instance, steps_data)

        return instance
#endregion Lesson Serializers


class LessonAuthenticatedSerializer(LessonSerializer):

    state = serializers.SerializerMethodField()

    class Meta(LessonSerializer.Meta):
        fields = LessonSerializer.Meta.fields + ('state', )

    def get_state(self, obj):
        """Returns the lesson state of the current user"""
        #see documentation at ProjectClassroomAuthenticatedMixin.

        if getattr(obj, 'user_registration', None) is not None:
            state = obj.user_registration[0] if obj.user_registration else None
        else:
            state = obj.registrations.filter(project_state__user=self.context.get('request').user).first()

        if not state:
            return None
        field_serializer = LessonStateSerializer(instance=state)
        field_serializer.parent = self  #connect serializer field to this serializer
        field_serializer.field_name = 'state'
        return field_serializer.data


class NotificationSerializer(serializers.ModelSerializer):
    actor = serializers.SerializerMethodField()
    target = serializers.SerializerMethodField()
    subject = serializers.SerializerMethodField()
    additionalData = serializers.DictField(source='data')

    class Meta:
        model = Notification
        fields = (
            'id',
            'description',
            'actor',
            'verb',
            'target',
            'subject',
            'additionalData',
            'level',
            'unread',
            'timestamp',
        )

    def _get_object_representation(self, value):
        if value is None:
            return None

        view_name = None
        view_kwargs = {}
        if isinstance(value, get_user_model()):
            view_name = 'api:user-detail'
            view_kwargs.update({
                'pk': value.pk,
            })
        elif isinstance(value, Lesson):
            view_name = 'api:project-lesson-detail'
            view_kwargs.update({
                'pk': value.pk,
                'project_pk': value.project_id,
            })
        elif isinstance(value, Project):
            view_name = 'api:project-detail'
            view_kwargs.update({
                'pk': value.pk,
            })
        elif isinstance(value, Classroom):
            view_name = 'api:classroom-detail'
            view_kwargs.update({
                'pk': value.pk,
            })

        obj_json = {
            'id': value.pk,
            'model': value.__class__.__name__,
            'self': reverse(view_name, kwargs=view_kwargs, request=self.context.get('request'), format=self.context.get('format')),
        }
        return obj_json

    def get_actor(self, obj):
        return self._get_object_representation(obj.actor)
    def get_target(self, obj):
        return self._get_object_representation(obj.target)
    def get_subject(self, obj):
        return self._get_object_representation(obj.action_object)

    def notification_to_email_data(self, notification, mail_template=None):
        # Default notification to email data:
        email_data = self.to_representation(notification)

        # Custom notification to email data for some notifications emails templates:
        if mail_template == 'IGNITE_notification_publish_mode_change':
            email_data['actor'].update({
                'title': notification.actor.title,
                'url': settings.IGNITE_FRONT_END_BASE_URL + 'app/project/%s/' %(notification.actor.id,),
            })
            if email_data['target']:
                email_data['target'].update({
                    'name': notification.target.name,
                })

        return email_data

class ViewInviteSerializer(serializers.ModelSerializer):
    project = serializers.PrimaryKeyRelatedField(read_only=True)
    hash = serializers.ReadOnlyField()

    class Meta:
        model = ViewInvite
        fields = (
            'project',
            'hash',
        )
