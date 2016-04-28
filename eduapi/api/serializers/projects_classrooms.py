from collections import OrderedDict

from django.utils.timezone import now as utc_now

from rest_framework import serializers, validators, exceptions
from rest_framework.fields import empty
from rest_framework.settings import api_settings

from .common import DynamicFieldsModelSerializer
from .fields import (
    URLField,
    ProjectHyperlinkedIdentityField,
    UserStateIdentityField,
    TagsField,
    HtmlField,
    JSONField,
)
from .mixins import (
    CheckBeforePublishMixin,
    ProjectClassroomAuthenticatedMixin,
    DraftSerializerMixin,
    ProjectDraftSerializerMixin,
)
from .users import (
    UserSerializer,
    OxygenUserSerializer,
)
from .serializers import (
    LessonSerializer,
    LessonStateSerializer,
)
from .validators import (
    InlineTeacherFileJSONValidator,
    SeparatorJSONValidator,
)

from ..models import (
    IgniteUser,

    Project,
    Classroom,
    ProjectState,
    ClassroomState,

    Lesson,
    ProjectInClassroom,
)
import querysets


class ProjectStateSerializer(DynamicFieldsModelSerializer, serializers.ModelSerializer):
    """
    Serializes a project state for the current user.
    """
    userId = serializers.ReadOnlyField(source='user_id')
    user = serializers.HyperlinkedRelatedField(view_name='api:user-detail', read_only=True, default=serializers.CreateOnlyDefault(serializers.CurrentUserDefault()))

    id = serializers.PrimaryKeyRelatedField(source='project', read_only=True)
    project = serializers.HyperlinkedRelatedField(view_name='api:project-detail', read_only=True)
    title = serializers.ReadOnlyField(source='project.title')
    cardImage = serializers.URLField(
        source='project.card_image',
        read_only=True,
        max_length=500,
    )
    difficulty = serializers.ReadOnlyField(source='project.difficulty')
    isCompleted = serializers.BooleanField(
        source='is_completed',
        read_only=True,
    )
    enrolltime = serializers.ReadOnlyField(source='added')

    # The self URL should point to the /user/:id/state/ because this API can
    # be accessed both by /me/ and by the user's guardians.
    self = UserStateIdentityField(
        lookup_field='project_id',
        pk_url_kwarg='project_pk',
        view_name='api:user-project-state-detail'
    )

    lessonStates = LessonStateSerializer(
        source='lesson_states',
        read_only=True,
		many=True,
    )

    numberOfProjectLessons = serializers.IntegerField(source='project.lesson_count', read_only=True)
    numberOfEnrolledLessons = serializers.IntegerField(source='enrolled_lessons_count', read_only=True)
    numberOfCompletedLessons = serializers.IntegerField(source='completed_lessons_count', read_only=True)

    updated = serializers.DateTimeField(read_only=True)

    class Meta:
        model = ProjectState
        fields = (
            'id',
            'project',
            'userId',
            'user',
            'title',
            'cardImage',
            'difficulty',
            'self',
            'enrolltime',
            'isCompleted',
            'numberOfProjectLessons',
            'numberOfEnrolledLessons',
            'numberOfCompletedLessons',
            'updated',

            #removable fields
            'lessonStates',
        )
        dropfields = (
            'lessonStates',
        )

    def __init__(self, *args, **kwargs):
        super(ProjectStateSerializer, self).__init__(*args, **kwargs)

        context = kwargs.get('context', {})

        #if 'project' is in context, then make it "id" default, otherwise make "id" field required:
        project = context.get('project')
        if project:
            self.fields['id'].default = project
        else:
            self.fields['id'].read_only = False
            self.fields['id'].required = True
            self.fields['id'].queryset = Project.objects.all()


class ProjectSerializer(ProjectClassroomAuthenticatedMixin, CheckBeforePublishMixin, ProjectDraftSerializerMixin, DynamicFieldsModelSerializer):

    bannerImage = URLField(
        source='banner_image',
        label='Banner Image',
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text='A URL to the project\'s banner image',
        max_length=500,
    )
    cardImage = URLField(
        source='card_image',
        label='Card Image',
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text='A URL to the project\'s card image',
        max_length=500,
    )

    id = serializers.ReadOnlyField()

    publishMode = serializers.ChoiceField(source='publish_mode', choices=Project.PUBLISH_MODES, required=False)
    publishDate = serializers.ReadOnlyField(source='publish_date')
    minPublishDate = serializers.DateTimeField(source='min_publish_date', allow_null=True, required=False)

    numberOfStudents = serializers.IntegerField(source='students_count', read_only=True)
    numberOfLessons = serializers.IntegerField(source='lesson_count', read_only=True)

    added = serializers.DateTimeField(read_only=True)
    updated = serializers.DateTimeField(read_only=True)

    author = UserSerializer(source='owner', read_only=False, default=serializers.CreateOnlyDefault(serializers.CurrentUserDefault()))
    currEditor = UserSerializer(source='current_editor', required=False, allow_null=True)

    extra = JSONField(
        label='Extra',
        required=False,
        allow_null=True,
        style={'input_type': 'textarea'},
        help_text='A JSON field that stores extra data for the project and its lessons',
    )

    self = ProjectHyperlinkedIdentityField(view_name='api:project-detail', draft_view_name='api:project-draft-detail')

    permission = serializers.SerializerMethodField()
    isEditor = serializers.SerializerMethodField()

    isSearchable = serializers.ReadOnlyField(source='is_searchable')

    lock = serializers.ReadOnlyField()
    lockMessage = serializers.ReadOnlyField(source="lock_message")

    #removable fields
    state = serializers.SerializerMethodField()
    lessonsIds = serializers.PrimaryKeyRelatedField(
        queryset=Lesson.objects.all(),
        source='lessons',
        many=True,
        read_only=False,
        required=False,
    )
    lessons = LessonSerializer(many=True, read_only=True, required=False)
    enrolled = serializers.SerializerMethodField('get_enrolled_state')

    tags = TagsField(model_field=Project._meta.get_field('tags'), required=False, allow_blank=True)

    numberOfProjectEditors = serializers.IntegerField(source='owner.editors_count', read_only=True, required=False)

    # Teacher info section is assembled from various project fields to single object/section.
    # It inherits DraftSerializerMixin which handles draft editable fields and generates diff fields inline.
    class TeachersInfoSerializer(DraftSerializerMixin, serializers.ModelSerializer):
        ngss =                  serializers.ListField(
                                    # source='ngss',
                                    child=serializers.ChoiceField(choices=Project.NGS_STANDARDS),
                                    required=False,
                                    allow_null=True,
                                )
        ccss =                  serializers.ListField(
                                    # source='ccss',
                                    child=serializers.ChoiceField(choices=Project.CCS_STANDARDS),
                                    required=False,
                                    allow_null=True,
                                )
        prerequisites =         HtmlField(
                                    # source='prerequisites',
                                    required=False,
                                    allow_null=True,
                                    allow_blank=True,
                                    style={'input_type': 'textarea'},
                                )
        tips =                  HtmlField(
                                    source='teacher_tips',
                                    required=False,
                                    allow_null=True,
                                    allow_blank=True,
                                    style={'input_type': 'textarea'},
                                )
        additionalResources =   HtmlField(
                                    source='teacher_additional_resources',
                                    required=False,
                                    allow_blank=True,
                                    style={'input_type': 'textarea'},
                                )
        teachersFiles =         serializers.ListField(
                                    source='teachers_files_list',
                                    child=JSONField(validators=(InlineTeacherFileJSONValidator(), )),
                                    required=False,
                                    allow_null=True,
                                )
        skillsAcquired =        serializers.ListField(
                                    source='skills_acquired',
                                    child=serializers.CharField(max_length=100),
                                    required=False,
                                    allow_null=True,
                                )
        learningObjectives =    serializers.ListField(
                                    source='learning_objectives',
                                    child=serializers.CharField(max_length=100),
                                    required=False,
                                    allow_null=True,
                                )
        grades =                serializers.ListField(
                                    source='grades_range',
                                    child=serializers.ChoiceField(choices=Project.GRADES),
                                    required=False,
                                    allow_null=True,
                                )
        subject =               serializers.ListField(
                                    # source='subject',
                                    child=serializers.ChoiceField(choices=Project.SUBJECTS),
                                    required=False,
                                    allow_null=True,
                                )
        technology =            serializers.ListField(
                                    # source='technology',
                                    child=serializers.ChoiceField(choices=Project.TECHNOLOGY),
                                    required=False,
                                    allow_null=True,
                                )

        class FourCSSerializer(DraftSerializerMixin, serializers.ModelSerializer):
            creativity =            HtmlField(
                                        source='four_cs_creativity',
                                        required=False,
                                        allow_null=True,
                                        allow_blank=True,
                                        style={'input_type': 'textarea'},
                                        max_length=250,
                                    )
            critical =              HtmlField(
                                        source='four_cs_critical',
                                        required=False,
                                        allow_null=True,
                                        allow_blank=True,
                                        style={'input_type': 'textarea'},
                                        max_length=250,
                                    )
            communication =         HtmlField(
                                        source='four_cs_communication',
                                        required=False,
                                        allow_null=True,
                                        allow_blank=True,
                                        style={'input_type': 'textarea'},
                                        max_length=250,
                                    )
            collaboration =         HtmlField(
                                        source='four_cs_collaboration',
                                        required=False,
                                        allow_null=True,
                                        allow_blank=True,
                                        style={'input_type': 'textarea'},
                                        max_length=250,
                                    )

            class Meta:
                model = Project
                fields = (
                    'creativity',
                    'critical',
                    'communication',
                    'collaboration',
                )
        fourCS = FourCSSerializer(source='*', required=False)

        class Meta:
            model = Project
            fields = (
                'ngss',
                'ccss',
                'prerequisites',
                'tips',
                'fourCS',
                'additionalResources',
                'teachersFiles',
                'skillsAcquired',
                'learningObjectives',
                'grades',
                'subject',
                'technology',
            )
    teacherInfo = TeachersInfoSerializer(source='*', required=False)

    state_serializer = ProjectStateSerializer

    class Meta:
        model = Project
        fields = (
            'id',
            'self',

            'publishMode',
            'publishDate',
            'minPublishDate',

            'title',
            'description',
            'bannerImage',
            'cardImage',

            'duration',
            'age',
            'difficulty',
            'license',
            'language',

            'numberOfLessons',
            'numberOfStudents',
            'numberOfProjectEditors',

            'teacherInfo',

            'lessonsIds',

            'tags',

            'lock',
            'lockMessage',

            'author',
            'permission',
            'isEditor',

            'isSearchable',

            'currEditor',

            'extra',

            'added',
            'updated',

            #removable fields
            'state',
            'lessonsIds',
            'lessons',
            'enrolled',
        )
        dropfields = (
            'lessons',
            'lessonsIds',
            'state',
            'enrolled',
        )
        required_on_publish = {
            'bannerImage': 'banner_image',
            'cardImage': 'card_image',
            'duration': 'duration',
            'age': 'age',
            'difficulty': 'difficulty',
            'license': 'license',

            # Teacher Info required fields before publishing:
            'teacherInfo.ngss': 'ngss',
            'teacherInfo.ccss': 'ccss',
            'teacherInfo.fourCS.creativity': 'four_cs_creativity',
            'teacherInfo.fourCS.critical': 'four_cs_critical',
            'teacherInfo.fourCS.communication': 'four_cs_communication',
            'teacherInfo.fourCS.collaboration': 'four_cs_collaboration',
            'teacherInfo.skillsAcquired': 'skills_acquired',
            'teacherInfo.learningObjectives': 'learning_objectives',
            'teacherInfo.grades': 'grades_range',
            'teacherInfo.subject': 'subject',
            'teacherInfo.technology': 'technology',
        }
        # Only fields editable for some publish modes:
        only_editable_fields_for_review_mode = only_editable_fields_for_ready_mode = (
            'publishMode',
            'minPublishDate',
        )

    def __init__(self, *args, **kwargs):
        super(ProjectSerializer, self).__init__(*args, **kwargs)

        #set author.id field to be writable:
        author_id_field = self.fields['author'].fields['id']
        author_id_field.read_only = False

        #set author.id field to be writable:
        current_editor_id_field = self.fields['currEditor'].fields['id']
        current_editor_id_field.read_only = False

        #if embed 'lessons' and 'draft'/'origin', then allow 'draft' field for lessons list:
        if 'lessons' in self.fields:
            context = kwargs.get('context', {})
            allowed = context.get('allowed', [])
            embed_related_kwargs = {
                'use_draft_instance': self.use_draft_instance,
            }
            if 'draft' in allowed:
                embed_related_kwargs['context'] = {'allowed': ['draft']}
            if 'origin' in allowed:
                embed_related_kwargs['context'] = {'allowed': ['origin']}
            self.fields['lessons'] = LessonSerializer(many=True, read_only=True, required=False, **embed_related_kwargs)

    def check_before_publish(self, instance, attrs):
        # Regular check instance before publish:
        errors = super(ProjectSerializer, self).check_before_publish(instance, attrs)

        # Additional check of lessons before publish:
        lessons = instance.lessons.all() if instance else []

        # Check that has at least 1 lesson before publishing:
        if not len(lessons):
            errors['lessons'] = {
                api_settings.NON_FIELD_ERRORS_KEY: ['Add at least 1 lesson']
            }
        # Check that all of the lessons are valid for publish:
        else:
            lesson_serializer = LessonSerializer()
            lessons_errors = {}
            for lesson in lessons:
                #if lesson has errors add it to the lessons errors dict:
                lesson_errors = lesson_serializer.check_before_publish(lesson, {})
                if lesson_errors:
                    lessons_errors[lesson.id] = lesson_errors
            if lessons_errors:
                errors['lessons'] = lessons_errors

        return errors

    def get_permission(self, obj):
        """Get the permission that the user has over this object"""
        req_hash = self.context['request'].QUERY_PARAMS.get('hash', None)
        return obj.get_permission_for_user(self.context['request'].user, view_hash=req_hash)

    def get_isEditor(self, obj):
        """Boolean whether the current user is an editor of this object"""
        return obj.is_editor(self.context['request'].user)

    def get_draft_data(self, origin_obj):
        ret = super(ProjectSerializer, self).get_draft_data(origin_obj)
        if ret is not None:
            ret['publishMode'] = self.fields['publishMode'].to_representation(origin_obj.draft_object.publish_mode)
            ret['currEditor'] = self.fields['currEditor'].to_representation(origin_obj.draft_object.current_editor) if origin_obj.draft_object.current_editor else None
        return ret

    def get_origin_data(self, draft_obj):
        ret = super(ProjectSerializer, self).get_origin_data(draft_obj)
        if ret is not None:
            ret['publishMode'] = self.fields['publishMode'].to_representation(draft_obj.draft_origin.publish_mode)
        return ret

    def validate_lessonsIds(self, value):
        #get the list of lessons in the project:
        lessons = list(self.instance.lessons.all()) if self.instance else []

        # Do not allow to add/remove lessons through 'lessonsIds' field:
        lessons_ordered_ids = [x.id for x in value]
        if set(lessons_ordered_ids) != set([x.id for x in lessons]):
            raise serializers.ValidationError('This field is only for changing lessons order, not to add/remove lessons. All lessons of the project must be in the list.')

        return value

    def validate_currEditor(self, value):
        current_editor_error = serializers.ValidationError({
            'id': ['You can not apply random user ID. Only current user is allowed.']
        })

        # Disable edit lock when publish mode is not edit:
        if self.instance is not None and self.instance.publish_mode != Project.PUBLISH_MODE_EDIT:
            raise serializers.ValidationError({
                api_settings.NON_FIELD_ERRORS_KEY: ['It is not allowed to edit lock the project when it is not in edit mode.'],
            })

        # get current editor id either from IgniteUser object or dict with 'id' field:
        if value is not None:
            current_editor_id = value.id if isinstance(value, IgniteUser) else value.get('id')
            # require inline 'id' field:
            if not current_editor_id:
                raise current_editor_error

            if current_editor_id == self.context['request'].user.id:
                value = self.context['request'].user
            elif not current_editor_id:
                value = None
            else:
                raise current_editor_error

        return value

    def validate_author(self, value):
        author_error = serializers.ValidationError({'id': ['Author can be set either to you or one of your delegators.']})

        # get owner id either from IgniteUser object or dict with 'id' field:
        owner_id = value.id if isinstance(value, IgniteUser) else value.get('id')

        # require inline 'id' field:
        if not owner_id:
            raise author_error

        # validate owner is set either to the request user logged in or one of her delegators:
        request_user = self.context['request'].user
        if owner_id == request_user.id:
            value = request_user
        else:
            # Get author user from allowed authors queryset:
            allowed_authors_qs = request_user.delegators.all()
            author_error_for_allowed = author_error
            if request_user.is_superuser:
                allowed_authors_qs = IgniteUser.objects.filter(is_child=False)
                author_error_for_allowed = serializers.ValidationError({'id': ['Author must be an adult user.']})
            try:
                value = allowed_authors_qs.get(pk=owner_id)
            except IgniteUser.DoesNotExist:
                raise author_error_for_allowed
        return value

    def validate_extra(self, value):
        try:
            value = (self.instance or Project()).validate_extra_field(value)
        except ValueError as exc:
            raise serializers.ValidationError(exc.message)
        return value

    def validate_publishMode(self, value):
        """Add note for the non-standard method name."""
        user = self.context['request'].user
        core_publish_mode = getattr(self.instance, 'publish_mode', Project.PUBLISH_MODE_EDIT)

        # If attempt to change publish mode:
        if value != core_publish_mode:

            # New project created must be in edit mode:
            if not self.instance and value != Project.PUBLISH_MODE_EDIT:
                raise exceptions.ValidationError('New project cannot be created in any mode other than edit.')

            # Change to edit mode:
            if value == Project.PUBLISH_MODE_EDIT:
                if core_publish_mode in [Project.PUBLISH_MODE_REVIEW, Project.PUBLISH_MODE_READY]:
                    if not self.instance.can_reedit(user):
                        raise ChangePublishModePermissionDenied(core_publish_mode, value)
                else:
                    raise ChangePublishModeError(core_publish_mode, value)

            # Change to review mode:
            elif value == Project.PUBLISH_MODE_REVIEW:
                if core_publish_mode == Project.PUBLISH_MODE_EDIT:
                    if not self.instance.can_edit(user):
                        raise ChangePublishModePermissionDenied(core_publish_mode, value)
                elif core_publish_mode == Project.PUBLISH_MODE_READY:
                    if not self.instance.can_publish(user):
                        raise ChangePublishModePermissionDenied(core_publish_mode, value)
                else:
                    raise ChangePublishModeError(core_publish_mode, value)

            # Change to ready or published modes:
            elif value == Project.PUBLISH_MODE_READY or value == Project.PUBLISH_MODE_PUBLISHED:
                if core_publish_mode in [Project.PUBLISH_MODE_REVIEW, Project.PUBLISH_MODE_EDIT]:
                    checked_permission_publish = None
                    if core_publish_mode == Project.PUBLISH_MODE_EDIT:
                        if not self.instance.can_edit(user):
                            raise ChangePublishModePermissionDenied(core_publish_mode, value)
                        # Move publish mode to review to check publish permission and reset it back:
                        setattr(self.instance, 'publish_mode', Project.PUBLISH_MODE_REVIEW)
                        checked_permission_publish = self.instance.can_publish(user)
                        setattr(self.instance, 'publish_mode', core_publish_mode)
                    checked_permission_publish = self.instance.can_publish(user) if checked_permission_publish is None else checked_permission_publish
                    if not checked_permission_publish:
                        raise ChangePublishModePermissionDenied(core_publish_mode, value)
                else:
                    raise ChangePublishModeError(core_publish_mode, value)
                # Force to ready mode (if time to publish has come, it will be turned to published later on .validate()).
                value = Project.PUBLISH_MODE_READY

            # Forbid to change to any other publish mode:
            else:
                raise ChangePublishModeError(core_publish_mode, value)

        return value

    def validate_minPublishDate(self, value):
        user = self.context['request'].user

        # Only user with edit or re-edit permission on the project can set the minimum publish date (e.g: owner):
        if (
            self.instance and (  # if instance is None, then project is just being created
                self.instance.publish_mode not in [Project.PUBLISH_MODE_EDIT, Project.PUBLISH_MODE_REVIEW, Project.PUBLISH_MODE_READY] or
                (not self.instance.is_editor(user) and not self.instance.can_reedit(user))
            )
        ):
            raise serializers.ValidationError('You do not have permission to set minimum publish date.')

        return value

    def to_internal_value(self, data):
        # Before getting internal value, set the only editable fields:
        # Note: If using bulk serializer, before calling to .update() or .create() on the child,
        #       make sure to set the only_editable_fields or instance before converting to internal value.
        if not hasattr(self, 'only_editable_fields'):
            cur_publish_mode = getattr(self.instance, 'publish_mode', Project.PUBLISH_MODE_EDIT)
            self.only_editable_fields = getattr(self.Meta, 'only_editable_fields_for_%s_mode' % cur_publish_mode, None)

        # If only_editable_fields is set, then make sure that any declared writable field that is not in the only
        # editable fields, does not present in data - otherwise throw validation error:
        if (
            self.only_editable_fields is not None and
            isinstance(data, dict) and
            not getattr(getattr(self.context.get('request'), 'user', None), 'is_superuser', None)  #allow superuser to always edit all fields
        ):
            for key, field in data.items():
                if key in self.fields and key not in self.only_editable_fields and not self.fields[key].read_only:
                    raise exceptions.ValidationError({
                        api_settings.NON_FIELD_ERRORS_KEY: [
                            'Only the following fields are editable for this project: %s' %(', '.join(self.only_editable_fields),)
                        ]
                    })

        return super(ProjectSerializer, self).to_internal_value(data)

    def _validate_attrs_with_instance(self, attrs, instance=None):
        '''
        Object/Instance level validation.

        Checks that the project is valid when published.
        '''
        errors = {}

        # Get 'publish_mode' flag:
        publish_mode = attrs.get('publish_mode') or getattr(instance, 'publish_mode', Project.PUBLISH_MODE_EDIT)
        # publish_mode = getattr(self.instance, 'publish_mode', Project.PUBLISH_MODE_EDIT)

        # Publish mode is above edit:
        if publish_mode != Project.PUBLISH_MODE_EDIT:
            # Check project before publish
            publish_errors = self.check_before_publish(instance, attrs)

            # Temporarily remove teacherInfo publish errors for instance that is already published:
            # (This is required to allow changes for existing published projects, until all are valid).
            if instance.publish_mode == Project.PUBLISH_MODE_PUBLISHED:
                publish_errors.pop('teacherInfo', None)

            if publish_errors:
                # Export publish errors to publishErrors
                errors.update({
                    'publishMode': ['There are errors to fix before project can be published.'],
                    'publishErrors': publish_errors,
                })

            else:
                # Reset current editor
                attrs['current_editor'] = None

                # Publish mode is ready
                if publish_mode == Project.PUBLISH_MODE_READY:
                    # If minimum publish date has passed, then move project to published mode
                    min_publish_date = attrs.get('min_publish_date', getattr(instance, 'min_publish_date', None))
                    if not min_publish_date or min_publish_date < utc_now():
                        attrs['publish_mode'] = Project.PUBLISH_MODE_PUBLISHED

        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def _save_lessons_order(self, instance, lessons_data):
        #if None, do nothing:
        if lessons_data is None:
            return

        # Set new lessons ordered list:
        Lesson().save_container_list_order(
            [x.pk for x in lessons_data],
            container_key=instance,
            save_kwargs={'change_updated_field': False}
        )

        # This is sort of an hack. We update the lessons in the DB, but
        # the lessons are not updated on "instance" which already has
        # the results prefetched. If we delete the prefetched results from
        # the cache, instance's lessons will be updated.
        getattr(instance, '_prefetched_objects_cache', {}).pop('lessons', None)

    def update(self, instance, validated_data):
        '''
        Delete all objects that have a manytomany relationship with this object.

        The reason is that the save_object method of the generic Serializer will 
        create these objects anew.
        '''
        validated_data = self._validate_attrs_with_instance(validated_data, instance)

        old_publish_mode = instance.publish_mode

        lessons_data = validated_data.pop('lessons', None)

        instance = super(ProjectSerializer, self).update(instance, validated_data)

        self._save_lessons_order(instance, lessons_data)

        # If publish_mode was changed:
        new_publish_mode = getattr(instance, 'publish_mode', None)
        if new_publish_mode != old_publish_mode:

            # Update original instance:
            if not self.use_draft_instance:
                #make notification for owner when publish_mode was changed:
                project_publish_modes_dict = dict(Project.PUBLISH_MODES)
                notify_kwargs = {
                    'target': self.context['request'].user,
                    'description': 'Project "%s" has moved from "%s" to "%s".' %(instance.title, project_publish_modes_dict.get(instance.publish_mode), project_publish_modes_dict.get(old_publish_mode)),
                    'publishMode': instance.publish_mode,
                    'oldPublishMode': old_publish_mode,
                }

                #if changed publish mode to published, then set publish_date to updated value:
                if new_publish_mode == Project.PUBLISH_MODE_PUBLISHED:
                    notify_kwargs['publishDate'] = instance.publish_date.strftime('%Y-%m-%d %H:%M'),

                #notify owner:
                instance.notify_owner(
                    'project_publish_mode_change_by_target',
                    notify_kwargs,
                    send_mail_with_template='IGNITE_notification_publish_mode_change',
                )

            # Update draft instance:
            else:
                #make notification for owner when draft publish_mode was changed:
                instance_origin = instance.draft_origin
                project_publish_modes_dict = dict(Project.PUBLISH_MODES)
                notify_kwargs = {
                    'target': self.context['request'].user,
                    'description': 'The changes to project "%s" have moved from "%s" to "%s".' %(instance.title, project_publish_modes_dict.get(instance.publish_mode), project_publish_modes_dict.get(old_publish_mode)),
                    'publishMode': instance_origin.publish_mode,
                    'publishDate': instance_origin.publish_date.strftime('%Y-%m-%d %H:%M'),
                    'draftPublishMode': instance.publish_mode,
                    'draftOldPublishMode': old_publish_mode,
                    'draftDiff': {
                        'id': instance.id,
                        'title': instance.title,
                        'diffFields': instance.draft_diff_fields(),
                        'lessons': [{
                                        'id': lesson.id,
                                        'title': lesson.draft_object.title,
                                        'diffFields': lesson.draft_diff_fields(),
                                        'steps': [{
                                                      'id': step.id,
                                                      'title': step.draft_object.title,
                                                      'diffFields': step.draft_diff_fields(),
                                                  } for step in lesson.steps.all() if step.has_draft]
                                    } for lesson in instance_origin.lessons.all() if lesson.has_draft]
                    },
                }

                #if changed publish mode to published on draft, then apply draft:
                if new_publish_mode == Project.PUBLISH_MODE_PUBLISHED:
                    instance.draft_apply()
                    instance.draft_discard()
                    notify_kwargs['description'] += ' The changes have been applied and are now live.'
                    notify_kwargs['draftAppliedDate'] = instance_origin.updated.strftime('%Y-%m-%d %H:%M')

                #notify owner:
                instance_origin.notify_owner(
                    'project_draft_mode_changed_by_target',
                    notify_kwargs,
                    send_mail_with_template='IGNITE_notification_publish_mode_change',
                )

        return instance

    def create(self, validated_data):
        validated_data = self._validate_attrs_with_instance(validated_data)
        instance = super(ProjectSerializer, self).create(validated_data)
        return instance


class ProjectWithOrderSerializer(ProjectSerializer):
    '''
    The same as ProjectSerializer, but adds an order field to mark the order
    of the project in the project.
    '''

    order = serializers.IntegerField(min_value=0, allow_null=True, required=False)

    class Meta(ProjectSerializer.Meta):
        fields = ProjectSerializer.Meta.fields + ('order',)

    def __init__(self, *args, **kwargs):
        super(ProjectWithOrderSerializer, self).__init__(*args, **kwargs)

        #make all parent serializer fields as read-only:
        for field_name, field in self.fields.items():
            if field_name in ProjectSerializer.Meta.fields and not field.read_only:
                field.read_only = True


class ChangePublishModePermissionDenied(exceptions.PermissionDenied):
    def __init__(self, from_publish_mode, to_publish_mode):
        super(ChangePublishModePermissionDenied, self).__init__(
            'You do not have permission to move the project from \'%s\' mode to \'%s\' mode.' %(
                from_publish_mode,
                to_publish_mode,
            )
        )
class ChangePublishModeError(serializers.ValidationError):
    def __init__(self, from_publish_mode, to_publish_mode):
        super(ChangePublishModeError, self).__init__(
            'Forbidden to move the project from \'%s\' mode to \'%s\' mode.' %(
                from_publish_mode,
                to_publish_mode,
            )
        )

class ProjectModeSerializer(CheckBeforePublishMixin, DraftSerializerMixin, serializers.ModelSerializer):
    publishMode = serializers.ChoiceField(source='publish_mode', choices=Project.PUBLISH_MODES)
    minPublishDate = serializers.DateTimeField(source='min_publish_date', allow_null=True)

    class Meta:
        model = Project
        fields = (
            'publishMode',
            'minPublishDate',
        )

    def __init__(self, *args, **kwargs):
        super(ProjectModeSerializer, self).__init__(*args, **kwargs)

        if self.use_draft_instance:
            # Totally remove minPublishDate which is not valid for draft project:
            self.fields.pop('minPublishDate')

    def check_before_publish(self, instance, attrs):
        project_serializer = ProjectSerializer()
        errors = project_serializer.check_before_publish(instance, {})
        return errors

    def validate_publishMode(self, value):
        """Add note for the non-standard method name."""
        user = self.context['request'].user
        core_publish_mode = getattr(self.instance, 'publish_mode', None)

        # If attempt to change publish mode:
        if value != core_publish_mode:

            # Change to edit mode:
            if value == Project.PUBLISH_MODE_EDIT:
                if core_publish_mode in [Project.PUBLISH_MODE_REVIEW, Project.PUBLISH_MODE_READY]:
                    if not self.instance.can_reedit(user):
                        raise ChangePublishModePermissionDenied(core_publish_mode, value)
                else:
                    raise ChangePublishModeError(core_publish_mode, value)

            # Change to review mode:
            elif value == Project.PUBLISH_MODE_REVIEW:
                if core_publish_mode == Project.PUBLISH_MODE_EDIT:
                    if not self.instance.can_edit(user):
                        raise ChangePublishModePermissionDenied(core_publish_mode, value)
                elif core_publish_mode == Project.PUBLISH_MODE_READY:
                    if not self.instance.can_publish(user):
                        raise ChangePublishModePermissionDenied(core_publish_mode, value)
                else:
                    raise ChangePublishModeError(core_publish_mode, value)

            # Change to ready or published modes:
            elif value == Project.PUBLISH_MODE_READY or value == Project.PUBLISH_MODE_PUBLISHED:
                if core_publish_mode in [Project.PUBLISH_MODE_REVIEW, Project.PUBLISH_MODE_EDIT]:
                    checked_permission_publish = None
                    if core_publish_mode == Project.PUBLISH_MODE_EDIT:
                        if not self.instance.can_edit(user):
                            raise ChangePublishModePermissionDenied(core_publish_mode, value)
                        # Move publish mode to review to check publish permission and reset it back:
                        setattr(self.instance, 'publish_mode', Project.PUBLISH_MODE_REVIEW)
                        checked_permission_publish = self.instance.can_publish(user)
                        setattr(self.instance, 'publish_mode', core_publish_mode)
                    checked_permission_publish = self.instance.can_publish(user) if checked_permission_publish is None else checked_permission_publish
                    if not checked_permission_publish:
                        raise ChangePublishModePermissionDenied(core_publish_mode, value)
                else:
                    raise ChangePublishModeError(core_publish_mode, value)
                # Force to ready mode (if time to publish has come, it will be turned to published later on .validate()).
                value = Project.PUBLISH_MODE_READY

            # Forbid to change to any other publish mode:
            else:
                raise ChangePublishModeError(core_publish_mode, value)

        return value

    def validate_minPublishDate(self, value):
        user = self.context['request'].user

        # Only user with edit or re-edit permission on the project can set the minimum publish date (e.g: owner):
        if (
            self.instance.publish_mode not in [Project.PUBLISH_MODE_EDIT, Project.PUBLISH_MODE_REVIEW, Project.PUBLISH_MODE_READY] or
            (not self.instance.is_editor(user) and not self.instance.can_reedit(user))
        ):
            raise serializers.ValidationError('You do not have permission to set minimum publish date.')

        return value

    def to_internal_value(self, data):
        # Assert instance exists (always update):
        if not self.instance:
            raise serializers.ValidationError('Project instance does not exist!')

        return super(ProjectModeSerializer, self).to_internal_value(data)

    def _validate_attrs_with_instance(self, attrs, instance=None):
        assert instance, (
            'Project instance must be used to change publish mode.'
        )

        publish_mode = attrs.get('publish_mode', getattr(instance, 'publish_mode', None))

        # Publish mode is above edit:
        if publish_mode != Project.PUBLISH_MODE_EDIT:
            # Check project before publish:
            project_serializer = ProjectSerializer()
            errors = project_serializer.check_before_publish(instance, {})
            if errors:
                # Export publish errors to 'publishErrors'
                raise serializers.ValidationError({'publishErrors': [errors]})

            # Reset current editor:
            attrs['current_editor'] = None

        # Publish mode is ready
        if publish_mode == Project.PUBLISH_MODE_READY:
            # If minimum publish date has passed, then move project to published mode
            min_publish_date = attrs.get('min_publish_date', getattr(instance, 'min_publish_date', None))
            if not min_publish_date or min_publish_date < utc_now():
                attrs['publish_mode'] = Project.PUBLISH_MODE_PUBLISHED

        return attrs

    def update(self, instance, validated_data):
        #Note: This serializer is not used with .create() so no need to override .create() method.
        validated_data = self._validate_attrs_with_instance(validated_data, instance)

        old_publish_mode = getattr(instance, 'publish_mode', None)
        validated_data['publish_date'] = None  #set publish_date to None

        instance = super(ProjectModeSerializer, self).update(instance, validated_data)

        #if publish_mode was changed:
        new_publish_mode = getattr(instance, 'publish_mode', None)
        if new_publish_mode != old_publish_mode:

            # Update original instance:
            if not self.use_draft_instance:
                #make notification for owner when publish_mode was changed:
                project_publish_modes_dict = dict(Project.PUBLISH_MODES)
                notify_kwargs = {
                    'target': self.context['request'].user,
                    'description': 'Project "%s" has moved from "%s" to "%s".' %(instance.title, project_publish_modes_dict.get(instance.publish_mode), project_publish_modes_dict.get(old_publish_mode)),
                    'publishMode': instance.publish_mode,
                    'oldPublishMode': old_publish_mode,
                }

                #if changed publish mode to published, then set publish_date to updated value:
                if new_publish_mode == Project.PUBLISH_MODE_PUBLISHED:
                    notify_kwargs['publishDate'] = instance.publish_date.strftime('%Y-%m-%d %H:%M'),

                #notify owner:
                instance.notify_owner(
                    'project_publish_mode_change_by_target',
                    notify_kwargs,
                    send_mail_with_template='IGNITE_notification_publish_mode_change',
                )

            # Update draft instance:
            else:
                #make notification for owner when draft publish_mode was changed:
                instance_origin = instance.draft_origin
                project_publish_modes_dict = dict(Project.PUBLISH_MODES)
                notify_kwargs = {
                    'target': self.context['request'].user,
                    'description': 'The changes to project "%s" have moved from "%s" to "%s".' %(instance.title, project_publish_modes_dict.get(instance.publish_mode), project_publish_modes_dict.get(old_publish_mode)),
                    'publishMode': instance_origin.publish_mode,
                    'publishDate': instance_origin.publish_date.strftime('%Y-%m-%d %H:%M'),
                    'draftPublishMode': instance.publish_mode,
                    'draftOldPublishMode': old_publish_mode,
                    'draftDiff': {
                        'id': instance.id,
                        'title': instance.title,
                        'diffFields': instance.draft_diff_fields(),
                        'lessons': [{
                                        'id': lesson.id,
                                        'title': lesson.draft_object.title,
                                        'diffFields': lesson.draft_diff_fields(),
                                        'steps': [{
                                                      'id': step.id,
                                                      'title': step.draft_object.title,
                                                      'diffFields': step.draft_diff_fields(),
                                                  } for step in lesson.steps.all() if step.has_draft]
                                    } for lesson in instance_origin.lessons.all() if lesson.has_draft]
                    },
                }

                #if changed publish mode to published on draft, then apply draft:
                if new_publish_mode == Project.PUBLISH_MODE_PUBLISHED:
                    instance.draft_apply()
                    instance.draft_discard()
                    notify_kwargs['description'] += ' The changes have been applied and are now live.'
                    notify_kwargs['draftAppliedDate'] = instance_origin.updated.strftime('%Y-%m-%d %H:%M')

                #notify owner:
                instance_origin.notify_owner(
                    'project_draft_mode_changed_by_target',
                    notify_kwargs,
                    send_mail_with_template='IGNITE_notification_publish_mode_change',
                )

        return instance


class ClassroomSerializer(DynamicFieldsModelSerializer, serializers.ModelSerializer):

    id = serializers.ReadOnlyField()
    added = serializers.DateTimeField(read_only=True)
    updated = serializers.DateTimeField(read_only=True)
    author = UserSerializer(source='owner', read_only=True, default=serializers.CreateOnlyDefault(serializers.CurrentUserDefault()))
    # numberOfProjects = serializers.SerializerMethodField('get_projects_count')
    numberOfProjects = serializers.IntegerField(source='projects_count', read_only=True)
    # numberOfStudents = serializers.SerializerMethodField('get_registration_approved_count')
    numberOfStudents = serializers.IntegerField(source='students_approved_count', read_only=True)
    # numberOfStudentsPending = serializers.SerializerMethodField('get_registration_pending_count')
    numberOfStudentsPending = serializers.IntegerField(source='students_pending_count', read_only=True)
    # numberOfStudentsRejected = serializers.SerializerMethodField('get_registration_rejected_count')
    numberOfStudentsRejected = serializers.IntegerField(source='students_rejected_count', read_only=True)
    self = serializers.HyperlinkedIdentityField(view_name='api:classroom-detail')
    bannerImage = URLField(
        source='banner_image',
        label='Banner Image',
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text='A URL to the project\'s banner image',
        max_length=500,
    )
    cardImage = URLField(
        source='card_image',
        label='Card Image',
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text='A URL to the project\'s card image',
        max_length=500,
    )
    projectsIds = serializers.PrimaryKeyRelatedField(
        source='projects_ordered_list',
        queryset=Project.objects.all(),
        many=True,
        read_only=False,
        required=False,
        default=serializers.CreateOnlyDefault([]),
    )
    projects = ProjectWithOrderSerializer(
        source='projects_ordered_list',
        many=True,
        read_only=True,
    )
    projectsSeparators = serializers.ListField(
        source='projects_separators',
        child=JSONField(validators=(SeparatorJSONValidator() ,)),
        required=False,
        allow_null=True,
    )
    isArchived = serializers.BooleanField(source='is_archived', required=False)

    class Meta:
        model = Classroom
        fields = (
            'id',
            'self',

            'title',
            'author',
            'description',
            'bannerImage',
            'cardImage',
            'isArchived',

            'numberOfProjects',
            'numberOfStudents',
            'numberOfStudentsPending',
            'numberOfStudentsRejected',

            'projectsSeparators',

            'added',
            'updated',

            # removable fields
            'projectsIds',
            'projects',
        )
        dropfields = (
            'projectsIds',
            'projects',
        )

    def to_native(self, obj):
        #remove counters of students pending/rejected for non-owner user:
        request = self.context.get('request')
        if not request or not obj or request.user != obj.owner:
            self.fields.pop('numberOfStudentsPending', None)
            self.fields.pop('numberOfStudentsRejected', None)
        return super(ClassroomSerializer, self).to_native(obj)


    def _validate_projects_ordered_list(self, value):
        #validate projects:
        unpublished_projects_ids = []
        for idx, project in enumerate(value):
            #check if project is in edit mode:
            if project.publish_mode == Project.PUBLISH_MODE_EDIT:
                unpublished_projects_ids.append(project.id)

        # Check that the user is allowed to add the projects to the classroom
        user = self.context['request'].user
        unautherized_projects_ids = []
        for idx, project in enumerate(value):
            if not project.can_teach(user):
                unautherized_projects_ids.append(project.id)

        # Build error message, if necessary:
        error_message = ''
        if unpublished_projects_ids:
            error_message += 'Unpublished Projects: %s\n' % (
                ' .'.join([str(x) for x in unpublished_projects_ids]),
            )

        if unautherized_projects_ids:
            error_message += 'Projects with no "Teach" permission: %s\n' % (
                ' .'.join([str(x) for x in unautherized_projects_ids]),
            )

        if error_message:
            raise serializers.ValidationError(
                'You can\'t add the following projects to the classroom: \n' + error_message
            )

        return value

    def validate_projectsIds(self, value):
        value = self._validate_projects_ordered_list(value)
        return value

    def _validate_attrs_with_instance(self, attrs, instance=None):
        errors = {}

        # Validate projects separators, that each separator is in the range of the projects in the list:
        projects_separators = attrs.get('projects_separators')
        if projects_separators:
            # get number of projects:
            projects_ordered_list = attrs.get('projects_ordered_list') or getattr(instance, 'projects_ordered_list', None)
            num_projects = len(projects_ordered_list) if projects_ordered_list is not None else instance.projects.count() if instance else None
            if num_projects is None:
                errors['projectsSeparators'] = ['Project separators can not be used when no project exists.']
            else:
                for project_separator in projects_separators:
                    if project_separator['before'] >= num_projects:
                        errors['projectsSeparators'] = ['Project separators must be before any project order.']
                        break

        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def _save_projects_ordered_list(self, instance, projects_ordered_list):
        """Helper method that saves the projects list to the instance."""

        # Note: Make sure to update any attribute of the instance that is affected! If you use .extra() or .prefetch,
        #   then make sure that the nested instances will have the required attributes for the nested serializer!

        #if None, do nothing:
        if projects_ordered_list is None:
            return

        #mapping projects ordered list to re-use instances:
        mapping_projects_ordered_list = {p.pk: p for p in getattr(instance, 'projects_ordered_list', [])}

        #remove projects from classroom that are not in the list:
        ProjectInClassroom.objects.filter(
            classroom=instance,
        ).exclude(
            project__in=projects_ordered_list,
        ).delete()

        #save (update or create) the projects in classroom with their order:
        for idx, project in enumerate(projects_ordered_list):
            #switch project object in the list with the project object from instance (that might might have prefetches):
            instance_project = mapping_projects_ordered_list.get(project.pk)
            if instance_project:
                projects_ordered_list[idx] = instance_project
                project = instance_project

            #put the project in classroom in the right order according to its index in the list:
            project_in_classroom, _ = ProjectInClassroom.objects.update_or_create(
                classroom=instance,
                project=project,
                defaults={
                    'order': idx,
                }
            )

            #update the project 'order' attribute from the save project_in_classroom object:
            project.order = project_in_classroom.order

        #update instance projects ordered list:
        instance.projects_ordered_list = projects_ordered_list
        #manually update projects counter:
        instance.projects_count = len(projects_ordered_list)

    def create(self, validated_data):
        validated_data = self._validate_attrs_with_instance(validated_data)
        projects_ordered_list = validated_data.pop('projects_ordered_list', None)
        instance = super(ClassroomSerializer, self).create(validated_data)
        self._save_projects_ordered_list(instance, projects_ordered_list)
        return instance

    def update(self, instance, validated_data):
        validated_data = self._validate_attrs_with_instance(validated_data, instance)
        projects_ordered_list = validated_data.pop('projects_ordered_list', None)
        instance = super(ClassroomSerializer, self).update(instance, validated_data)
        self._save_projects_ordered_list(instance, projects_ordered_list)
        return instance


class ClassroomStateSerializer(DynamicFieldsModelSerializer, serializers.ModelSerializer):
    """
    Serializes a classroom state for the current user.
    """

    # Note: (user, classroom) is unique together.

    userId = serializers.ReadOnlyField(source='user_id')
    user = serializers.HyperlinkedRelatedField(view_name='api:user-detail', read_only=True, default=serializers.CreateOnlyDefault(serializers.CurrentUserDefault()))

    id = serializers.PrimaryKeyRelatedField(source='classroom', read_only=True)
    classroom = serializers.HyperlinkedRelatedField(view_name='api:classroom-detail', read_only=True)

    status = serializers.ChoiceField(choices=ClassroomState.STATUSES, read_only=True)

    title = serializers.ReadOnlyField(source='classroom.title')
    teacherName = serializers.ReadOnlyField(source='classroom.owner.name')
    teacherAvatar = serializers.ReadOnlyField(source='classroom.owner.avatar')
    cardImage = serializers.URLField(
        source='classroom.card_image',
        read_only=True,
        max_length=500,
    )
    enrolltime = serializers.ReadOnlyField(source='added')
    
    # The self URL should point to the /user/:id/state/ because this API can
    # be accessed both by /me/ and by the user's guardians.
    self = UserStateIdentityField(
        lookup_field='classroom_id',
        pk_url_kwarg='classroom_pk',
        view_name='api:user-classroom-state-detail'
    )

    projectStates = serializers.SerializerMethodField('get_projects_states_field')

    numberOfClassroomProjects = serializers.ReadOnlyField(source='classroom.projects_count')
    numberOfEnrolledProjects = serializers.ReadOnlyField(source='number_of_enrolled_projects')
    numberOfCompletedProjects = serializers.ReadOnlyField(source='number_of_completed_projects')

    updated = serializers.DateTimeField(read_only=True)

    class Meta:
        model = ClassroomState
        fields = (
            'id',
            'classroom',
            'userId',
            'user',
            'status',
            'title',
            'cardImage',
            'teacherName',
            'teacherAvatar',
            'self',
            'enrolltime',
            'numberOfClassroomProjects',
            'numberOfEnrolledProjects',
            'numberOfCompletedProjects',
            'updated',

            #removable fields
            'projectStates',
        )
        dropfields = [
            'projectStates',
        ]

    def __init__(self, *args, **kwargs):
        super(ClassroomStateSerializer, self).__init__(*args, **kwargs)

        context = kwargs.get('context', {})

        #if 'classroom' is in context, then make it "id" default, otherwise make "id" field required:
        classroom = context.get('classroom')
        if classroom:
            self.fields['id'].default = classroom
        else:
            self.fields['id'].read_only = False
            self.fields['id'].required = True
            self.fields['id'].queryset = Classroom.objects.all()

    def get_projects_states_field(self, obj):
        #Note: Since classroom state is connected to project states through classroom.projects.registrations which
        #   accesses data after ManyRelatedManager (projects), then it is impossible to use such kind of prefetched
        #   objects in an inlined serializer field as source.
        #   Now, since we only have a single classroom state, prefetch is not that useful, so we will get the project
        #   states via a queryset based on ClassroomState (get_projects_stats).

        #get and optimize projects states queryset:
        projects_states = obj.get_projects_states()
        projects_states = querysets.optimize_for_serializer_project_state(projects_states, with_counters=True)

        #get serializer data:
        field_serializer = ProjectStateSerializer(instance=projects_states, many=True)
        field_serializer.parent = self
        field_serializer.field_name = 'projectStates'
        return field_serializer.data

    def _validate_attrs_with_instance(self, attrs, instance=None):
        # Note: Field 'id' (source classroom) is required or has default, then this must be set:
        classroom_obj = attrs['classroom']

        # Check user is not the teacher of the classroom:
        if attrs['user'] == classroom_obj.owner:
            raise exceptions.PermissionDenied(detail='Teacher cannot be a student in his own classroom.')

        # new state is created or existing state status is rejected, then force set status to pending:
        if not instance or instance.status == ClassroomState.REJECTED_STATUS:
            #set status to pending:
            attrs['status'] = ClassroomState.PENDING_STATUS

        return attrs

    def update(self, instance, validated_data):
        validated_data = self._validate_attrs_with_instance(validated_data, instance)
        instance = super(ClassroomStateSerializer, self).update(instance, validated_data)
        return instance

    def create(self, validated_data):
        validated_data = self._validate_attrs_with_instance(validated_data)
        instance = super(ClassroomStateSerializer, self).create(validated_data)
        return instance


class ProjectAuthenticatedSerializer(ProjectSerializer):

    state_serializer = ProjectStateSerializer
    class Meta(ProjectSerializer.Meta):
        fields = ProjectSerializer.Meta.fields + ('enrolled', 'state')


class ProjectWithOrderAuthenticatedSerializer(ProjectWithOrderSerializer):

    state_serializer = ProjectStateSerializer
    class Meta(ProjectWithOrderSerializer.Meta):
        fields = ProjectWithOrderSerializer.Meta.fields + ('state', )


class ClassroomAuthenticatedSerializer(ProjectClassroomAuthenticatedMixin, ClassroomSerializer):

    enrolled = serializers.SerializerMethodField('get_enrolled_state')
    state = serializers.SerializerMethodField()

    state_serializer = ClassroomStateSerializer
    class Meta(ClassroomSerializer.Meta):
        fields = ClassroomSerializer.Meta.fields + ('enrolled', 'state')


class ClassroomCodeGeneratorSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField()
    self = serializers.HyperlinkedIdentityField(view_name='api:classroom-code-generator-detail', lookup_url_kwarg='classroom_pk')
    title = serializers.CharField(read_only=True)
    code = serializers.CharField(read_only=True)

    class Meta:
        model = Classroom
        fields = (
            'id',
            'self',
            'title',
            'code',
        )

class ClassroomCodeInviteSerializer(serializers.Serializer):
    message = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    invitees = serializers.ListField(
        child=serializers.EmailField(),
        required=True,
    )

    def create(self, obj, **kwargs):
        #NOTE: This serializer is not a model serializer, and obj parameter is actually a dict.
        #       Therefore, do not call super, since it treats obj as model and does obj.save().
        pass


class ClassroomCodeSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField()
    self = serializers.HyperlinkedIdentityField(view_name='api:classroom-code-detail', lookup_field='code', lookup_url_kwarg='classroom_code')
    author = OxygenUserSerializer(source='owner', read_only=True)
    bannerImage = URLField(source='banner_image', read_only=True)
    cardImage = URLField(source='card_image', read_only=True)

    joinUrl = serializers.HyperlinkedIdentityField(view_name='api:classroom-code-state-detail', lookup_field='code', lookup_url_kwarg='classroom_code')

    class Meta:
        model = Classroom
        fields = (
            'id',
            'self',

            'title',
            'author',
            'description',
            'bannerImage',
            'cardImage',

            'joinUrl',
        )
