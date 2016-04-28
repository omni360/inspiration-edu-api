from django.core.urlresolvers import reverse
from django.db.models import Prefetch, Q

from rest_framework import serializers
from rest_framework.settings import api_settings
from rest_framework.exceptions import ValidationError

from rest_framework_bulk.serializers import BulkSerializerMixin, BulkListSerializer
from api.emails import joined_classroom_email

from utils_app.counter import ExtendQuerySetWithSubRelated

from ..models import IgniteUser, ChildGuardian, ClassroomState, OwnerDelegate
from ..auth.oxygen_operations import OxygenOperations

from .mixins import (
    DynamicFieldsMixin,
)

from .fields import (
    UserStateIdentityField,
)


class UserSerializer(DynamicFieldsMixin, serializers.ModelSerializer):
    '''
    Serializes the IngiteUser model. Only displays information about the user
    that should be publicly available.
    All fields are defined as read_only by default.
    '''

    shortName = serializers.CharField(
        source='short_name',
        label='Short name',
        read_only=True,
        help_text='The name that the user would like to be called in short',
    )

    joined = serializers.DateTimeField(
        source='added',
        read_only=True,
        label='Date joined',
        help_text='Date user joined Project Ignite',
    )

    self = serializers.HyperlinkedIdentityField(view_name='api:user-detail')

    class Meta:
        model = IgniteUser
        fields = (
            'id',
            'self',
            'name',
            'shortName',
            'avatar',
            'description',
            'joined',
        )

    def __init__(self, *args, **kwargs):
        super(UserSerializer, self).__init__(*args, **kwargs)

        #make all UserSerializer fields read only:
        for field_name, field in self.fields.items():
            if field_name in UserSerializer.Meta.fields:
                field.read_only = True


class OxygenUserSerializer(UserSerializer):
    oxygenId = serializers.ReadOnlyField(source='oxygen_id')

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + (
            'oxygenId',
        )


class StudentSerializer(UserSerializer):
    class Meta(UserSerializer.Meta):
        pass

class ClassroomStudentListSerializer(BulkListSerializer, serializers.ListSerializer):
    def update(self, instance, validated_data):
        #if not POST or PUT (PUT-as-create, POST-as-update), use default BulkListSerializer.update():
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
            return super(ClassroomStudentListSerializer, self).update(instance, validated_data)

        #maps for id->instance:
        instance_mapping = {inst.id: inst for inst in instance}

        #perform creations and updates:
        ret = []
        for item_data in validated_data:
            inst = instance_mapping.get(item_data.get('id'))
            if inst is None:
                ret.append(self.child.create(item_data))
            else:
                ret.append(self.child.update(inst, item_data))

        return ret

class ClassroomStudentSerializer(BulkSerializerMixin, StudentSerializer):
    studentStatus = serializers.ChoiceField(source='student_status', choices=ClassroomState.STATUSES, default=ClassroomState.APPROVED_STATUS, read_only=False)

    class Meta(StudentSerializer.Meta):
        list_serializer_class = ClassroomStudentListSerializer
        fields = StudentSerializer.Meta.fields + (
            'studentStatus',
        )

    def __init__(self, *args, **kwargs):
        super(ClassroomStudentSerializer, self).__init__(*args, **kwargs)

        context = kwargs.get('context', {})

        #if 'user_pk' is not in context, then make it "id" default, otherwise make "id" field required:
        user_pk = context.get('user_pk')
        if user_pk:
            self.fields['id'].default = user_pk
        else:
            self.fields['id'].read_only = False
            self.fields['id'].required = True

        #get classroom from context:
        self.classroom = context.get('classroom')
        assert self.classroom is not None, (
            'Programming Error: %s must have \'classroom\' object in context!' % (self.__class__.__name__,)
        )

        #set allowed users queryset:
        self.allowed_users = self.Meta.model.objects.all()
        if not context['request'].user.is_superuser:
            self.allowed_users = self.allowed_users.filter(
                Q(pk__in=ClassroomState.objects.filter(classroom__owner=self.classroom.owner).values('user')) |  #students of the teacher (of any status)
                Q(pk__in=ChildGuardian.objects.filter(guardian=self.classroom.owner).values('child'))  #children of the teacher
            )

    def validate_id(self, value):
        #validate that user id is student or child of the classroom owner:
        if not self.allowed_users.filter(pk=value).exists():
            raise ValidationError('User is not student or child of the classroom owner.')
        return value

    def _save_student_data(self, student_id, student_validated_data):
        #create or update classroom state for the user, with the given status:
        student_state, _ = ClassroomState.objects.update_or_create(
            classroom=self.classroom,
            user_id=student_id,
            defaults={
                'status': student_validated_data['student_status'],
            }
        )

        return student_state

    def create(self, validated_data):
        student_state = self._save_student_data(validated_data['id'], validated_data)
        student = student_state.user
        student.student_status = student_state.status
        return student

    def update(self, instance, validated_data):
        student_state = self._save_student_data(instance.id, validated_data)
        student = instance
        student.student_status = student_state.status
        return student

    def delete(self):
        assert self.instance is not None, (
            'You cannot call .delete() on serializer without instance.'
        )

        #delete classroom state for the user [Note: (user, classroom) is unique]:
        try:
            classroom_state_obj = ClassroomState.objects.get(classroom=self.classroom, user=self.instance)
        except ClassroomState.DoesNotExist:
            pass
        else:
            classroom_state_obj.delete()


class StudentClassroomStateSerializerField(serializers.ModelSerializer):
    """
    Serializes a classroom state for a student, prefetch in student serializer.
    """
    classroomId = serializers.IntegerField(source='classroom_id', read_only=False)
    status = serializers.ChoiceField(choices=ClassroomState.STATUSES, read_only=False, required=False)
    enrolltime = serializers.ReadOnlyField(source='added')

    # The userStateUrl URL should point to the /user/:id/state/ because this API can
    # be accessed both by /me/ and by the user's guardians.
    studentStateUrl = UserStateIdentityField(
        lookup_field='classroom_id',
        pk_url_kwarg='classroom_pk',
        view_name='api:user-classroom-state-detail'
    )

    numberOfEnrolledProjects = serializers.ReadOnlyField(source='number_of_enrolled_projects')
    numberOfCompletedProjects = serializers.ReadOnlyField(source='number_of_completed_projects')

    class Meta:
        model = ClassroomState
        fields = (
            'classroomId',
            'status',
            'enrolltime',
            'studentStateUrl',
            'numberOfEnrolledProjects',
            'numberOfCompletedProjects',
        )
        validators = []

    def __init__(self, *args, **kwargs):
        super(StudentClassroomStateSerializerField, self).__init__(*args, **kwargs)

        # Add 'classroom' serializer field, and modify its fields:
        from api.serializers.projects_classrooms import ClassroomSerializer
        self.fields['classroom'] = ClassroomSerializer(read_only=True)

    def validate_classroomId(self, value):
        #assert got all parameters from context:
        student_id = self.context.get('student_id')
        assert student_id is not None, (
            '%s must have \'student_id\' in context!' % (self.__class__.__name__,)
        )
        student_classrooms_states_qs = self.context.get('student_classrooms_states_qs')
        assert student_classrooms_states_qs is not None, (
            '%s must have \'student_classrooms_states_qs\' in context!' % (self.__class__.__name__,)
        )

        #validate that student classroom state exists:
        if not student_classrooms_states_qs.filter(user_id=student_id, classroom_id=value).exists():
            raise ValidationError('Student is not enrolled to the classroom.')
        return value


class TeacherStudentListSerializer(BulkListSerializer, serializers.ListSerializer):

    def __init__(self, *args, **kwargs):
        kwargs['partial'] = False  #do not allow partial
        super(TeacherStudentListSerializer, self).__init__(*args, **kwargs)

    def update(self, instance, validated_data):
        """
        Currently we are not using update, as the student are not passed by ID, but instead are handled by order
        """
        #if not POST or PUT (PUT-as-create, POST-as-update), use default BulkListSerializer.update():
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
            return super(TeacherStudentListSerializer, self).update(instance, validated_data)

        #mapping id -> student:
        students_mapping = {student.id: student for student in instance}

        #only update students in instance:
        return_list = []
        for student_data in validated_data:
            student = students_mapping.get(student_data['id'], None)
            if not student:  #child .validate_id() should assure that validated data is directed to only updating students
                continue
            return_list.append(self.child.update(student, student_data))

        return return_list


class TeacherStudentSerializer(StudentSerializer):

    class Meta(StudentSerializer.Meta):
        validators = []
        list_serializer_class = TeacherStudentListSerializer

    def __init__(self, *args, **kwargs):
        kwargs['partial'] = False  #do not allow partial
        super(TeacherStudentSerializer, self).__init__(*args, **kwargs)

        # Add studentClassroomStates field:
        self.fields['studentClassroomStates'] = StudentClassroomStateSerializerField(source='student_classrooms_states', many=True, read_only=False, default=[])

        context = kwargs.get('context', {})

        #get 'teacher' from the context:
        self.teacher = context.get('teacher')
        assert self.teacher is not None, (
            'Programming Error: %s must have \'teacher\' object in context!' % (self.__class__.__name__,)
        )

        #get students classroom states queryset from context, otherwise set it to teacher's students queryset:
        self.students_classroom_states_qs = context.get('students_classroom_states_qs', ClassroomState.objects.filter(classroom__owner=self.teacher))

        #if 'student_pk' is not in context, then make it "id" default, otherwise make "id" field required:
        student_pk = context.get('student_pk')
        if student_pk:
            self.fields['id'].default = student_pk
        else:
            self.fields['id'].read_only = False
            self.fields['id'].required = True


    def validate_id(self, value):
        #check that id is in student classroom states:
        if not self.students_classroom_states_qs.filter(user=value).exists():
            raise ValidationError('Student is not found.')
        return value

    def to_internal_value(self, data):
        #validated student classroom states after validating current serializer:
        student_classroom_states_data = data.pop('studentClassroomStates', None)

        #validate current serializer:
        validated_data = super(TeacherStudentSerializer, self).to_internal_value(data)

        #student classroom states to internal value:
        student_id = validated_data['id']
        student_classroom_states_serializer = StudentClassroomStateSerializerField(
            data=student_classroom_states_data,
            many=True,
            context={
                'student_id': student_id,
                'student_classrooms_states_qs': self.students_classroom_states_qs.filter(user=student_id),
            },
        )
        # student_classroom_states_serializer.child.fields['classroomId'].queryset = Classroom.objects.filter(pk__in=self.students_classroom_states_qs.filter(user=student_id).values('classroom'))
        if not student_classroom_states_serializer.is_valid():
            raise ValidationError({
                'studentClassroomStates': student_classroom_states_serializer.errors,
            })
        validated_data['student_classrooms_states'] = student_classroom_states_serializer.validated_data

        return validated_data

    def _save_student_classroom_states(self, student, student_classrooms_states):
        #mapping classroom_id -> student classroom state instance:
        mapping_student_cs_list = {
            cs.classroom_id: cs for cs in student.student_classrooms_states
        }

        #update the student classroom states:
        student_cs_list = []
        for cs_data in student_classrooms_states:
            cs = mapping_student_cs_list.get(cs_data['classroom_id'])
            if cs:
                cs_status = cs_data.get('status', cs.status)
                if cs_status != cs.status:
                    cs.status = cs_status
                    cs.save()  #email is sent through ClassroomState.save() method
                student_cs_list.append(cs)
        student.student_classrooms_states = student_cs_list

    def update(self, instance, validated_data):
        student_classrooms_states = validated_data.pop('student_classrooms_states', [])
        self._save_student_classroom_states(instance, student_classrooms_states)
        return instance


class ChildOfGuardianListSerializer(serializers.ListSerializer):
    def create(self, validated_data):
        #map (child oxygen id, guardian oxygen id) -> item in validated_data:
        mapped_data = {
            (item['child'].oxygen_id, item['guardian'].oxygen_id): item for item in validated_data
        }
        mapped_result = {}

        #group serializer objects by guardians:
        guardians_children_grouped = {}
        for item in validated_data:
            guardian_children = guardians_children_grouped.setdefault(item['guardian'], [])
            guardian_children.append(item['child'])

        #make Oxygen operation to add children to the guardian:
        oxygen_operations = OxygenOperations()
        for guardian, guardian_children in guardians_children_grouped.items():
            moderated_children = oxygen_operations.add_guardian_children(
                guardian=guardian,
                moderated_children={
                    ChildGuardian.MODERATOR_PARENT: guardian_children
                },
            )
            #remove any failed item from validated_data:
            #TODO: Find a better way to keep the failed items and show errors and success in same list serializer.
            for child_oxygen_id, moderated_child_result in moderated_children[ChildGuardian.MODERATOR_PARENT].items():
                if moderated_child_result['state'] == 'SUCCESS':
                    mapped_result[moderated_child_result['child'].id] = moderated_child_result['child_guardian']

        #return list of child guardian instances for the list serializer:
        instance = [mapped_result[item['child'].id] for item in validated_data if item['child'].id in mapped_result]
        return instance


class ChildOfGuardianSerializer(BulkSerializerMixin, serializers.ModelSerializer):
    id = serializers.PrimaryKeyRelatedField(source='child', read_only=False, queryset=IgniteUser.objects.all())

    self = serializers.HyperlinkedRelatedField(source='child', view_name='api:user-detail', read_only=True)

    name = serializers.ReadOnlyField(source='child.name')
    shortName = serializers.ReadOnlyField(source='child.short_name')
    avatar = serializers.ReadOnlyField(source='child.avatar')
    description = serializers.ReadOnlyField(source='child.description')
    joined = serializers.DateTimeField(source='child.added', read_only=True)
    memberId = serializers.ReadOnlyField(source='child.member_id')
    email = serializers.ReadOnlyField(source='child.email')
    userType = serializers.CharField(source='child.user_type', required=False, allow_blank=True)

    guardianId = serializers.IntegerField(source='guardian_id', read_only=False)
    guardian = serializers.HyperlinkedRelatedField(view_name='api:user-detail', read_only=True)
    moderatorType = serializers.ChoiceField(source='moderator_type', choices=ChildGuardian.MODERATOR_TYPE_CHOICES, read_only=False, default=ChildGuardian.MODERATOR_PARENT)
    moderatedSince = serializers.DateTimeField(source='added', read_only=True)

    class Meta:
        model = ChildGuardian
        list_serializer_class = ChildOfGuardianListSerializer
        fields = (
            'id',
            'self',
            'name',
            'shortName',
            'avatar',
            'description',
            'joined',
            'memberId',
            'email',
            'userType',
            'guardianId',
            'guardian',
            'moderatorType',
            'moderatedSince',
        )

    def to_internal_value(self, data):
        ret = super(ChildOfGuardianSerializer, self).to_internal_value(data)

        #make sure the child is not yet moderated by the guardian:
        if ChildGuardian.objects.filter(child=ret['child'], guardian=ret['guardian']).exists():
            raise ValidationError({'id': ['Child is already moderated by the Moderator.']})

        return ret

    def validate_id(self, value):
        if not value.is_child:
            raise ValidationError('User is not a child.')
        return value


class ChildOfCurrentUserSerializer(ChildOfGuardianSerializer):
    '''
    Same as ChildOfGuardianSerializer, except that guardianId field is read-only.
    '''
    def __init__(self, *args, **kwargs):
        super(ChildOfCurrentUserSerializer, self).__init__(*args, **kwargs)
        self.fields['guardianId'].read_only = True
        self.fields['guardian'].default = serializers.CurrentUserDefault()


class DelegateOfOwnerSerializer(BulkSerializerMixin, serializers.ModelSerializer):
    id = serializers.PrimaryKeyRelatedField(source='user', read_only=False, queryset=IgniteUser.objects.all())

    self = serializers.HyperlinkedRelatedField(source='user', view_name='api:user-detail', read_only=True)

    name = serializers.ReadOnlyField(source='user.name')
    shortName = serializers.ReadOnlyField(source='user.short_name')
    avatar = serializers.ReadOnlyField(source='user.avatar')
    description = serializers.ReadOnlyField(source='user.description')
    joined = serializers.DateTimeField(source='user.added', read_only=True)
    memberId = serializers.ReadOnlyField(source='user.member_id')
    email = serializers.ReadOnlyField(source='user.email')

    delegatorId= serializers.IntegerField(source='owner_id', read_only=False)
    delegator = serializers.HyperlinkedRelatedField(source='owner', view_name='api:user-detail', read_only=True)
    delegatedSince = serializers.DateTimeField(source='added', read_only=True)

    class Meta:
        model = OwnerDelegate
        fields = (
            'id',
            'self',
            'name',
            'shortName',
            'avatar',
            'description',
            'joined',
            'memberId',
            'email',
            'delegatorId',
            'delegator',
            'delegatedSince',
        )

    def to_internal_value(self, data):
        ret = super(DelegateOfOwnerSerializer, self).to_internal_value(data)

        #make sure the user is not yet delegated by the owner delegator:
        if OwnerDelegate.objects.filter(user=ret['user'], owner=ret['owner']).exists():
            raise ValidationError({'id': ['User is already delegated by the owner.']})

        return ret

    def validate_id(self, value):
        if value.is_child:
            raise ValidationError('Child user cannot be delegated.')
        return value


class DelegateOfCurrentUserSerializer(DelegateOfOwnerSerializer):
    '''
    Same as ChildOfGuardianSerializer, except that guardianId field is read-only.
    '''
    def __init__(self, *args, **kwargs):
        super(DelegateOfCurrentUserSerializer, self).__init__(*args, **kwargs)
        self.fields['delegatorId'].read_only = True
        self.fields['delegator'].default = serializers.CurrentUserDefault()


class OwnerOfDelegateSerializer(BulkSerializerMixin, serializers.ModelSerializer):
    id = serializers.PrimaryKeyRelatedField(source='owner', read_only=False, queryset=IgniteUser.objects.all())

    self = serializers.HyperlinkedRelatedField(source='owner', view_name='api:user-detail', read_only=True)

    name = serializers.ReadOnlyField(source='owner.name')
    shortName = serializers.ReadOnlyField(source='owner.short_name')
    avatar = serializers.ReadOnlyField(source='owner.avatar')
    description = serializers.ReadOnlyField(source='owner.description')
    joined = serializers.DateTimeField(source='owner.added', read_only=True)
    memberId = serializers.ReadOnlyField(source='owner.member_id')
    email = serializers.ReadOnlyField(source='owner.email')

    delegateId= serializers.IntegerField(source='user_id', read_only=False)
    delegate = serializers.HyperlinkedRelatedField(source='user', view_name='api:user-detail', read_only=True)
    delegatedSince = serializers.DateTimeField(source='added', read_only=True)

    class Meta:
        model = OwnerDelegate
        fields = (
            'id',
            'self',
            'name',
            'shortName',
            'avatar',
            'description',
            'joined',
            'memberId',
            'email',
            'delegateId',
            'delegate',
            'delegatedSince',
        )

    def to_internal_value(self, data):
        ret = super(OwnerOfDelegateSerializer, self).to_internal_value(data)

        #make sure the user is not yet delegated by the owner delegator:
        if OwnerDelegate.objects.filter(owner=ret['owner'], user=ret['user']).exists():
            raise ValidationError({'id': ['Owner is already delegator of the user.']})

        return ret

    def validate_id(self, value):
        if value.is_child:
            raise ValidationError('Child user cannot delegate.')
        return value


class DelegatorOfCurrentUserSerializer(OwnerOfDelegateSerializer):
    '''
    Same as ChildOfGuardianSerializer, except that guardianId field is read-only.
    '''
    def __init__(self, *args, **kwargs):
        super(DelegatorOfCurrentUserSerializer, self).__init__(*args, **kwargs)
        self.fields['delegateId'].read_only = True
        self.fields['delegate'].default = serializers.CurrentUserDefault()


class FullUserSerializer(UserSerializer):
    '''
    Serializes IgniteUser instance with sensitive information. 

    Useful for retrieving data about oneself.
    '''

    memberId = serializers.CharField(
        source='member_id',
        label='Member ID',
        read_only=True,
        help_text='The Spark API Member ID of the user',
    )

    isChild = serializers.BooleanField(
        source='is_child',
        read_only=True
    )

    userType = serializers.CharField(source='user_type',
                                     required=False,
                                     allow_blank=True)

    isVerifiedAdult = serializers.BooleanField(
        source='is_verified_adult',
        read_only=True
    )

    isVerifiedChild = serializers.BooleanField(
        source='is_approved',
        read_only=True
    )

    isSuperuser = serializers.BooleanField(
        source='is_superuser',
        read_only=True
    )

    showAuthoringTooltips = serializers.BooleanField(
        source='show_authoring_tooltips',
        read_only=True,
    )

    self = serializers.SerializerMethodField('get_self_url')

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + (
            'memberId',
            'email',
            'isChild',
            'userType',
            'isVerifiedAdult',
            'isVerifiedChild',
            'isSuperuser',
            'showAuthoringTooltips',
        )

    def get_self_url(self, obj):
        return self.context.get('request', None).build_absolute_uri(reverse('api:me'))


class SparkDriveUserUpdateSerializer(serializers.Serializer):
    sessionId = serializers.CharField(write_only=True, required=False)
    secureSessionId = serializers.CharField(write_only=True, required=False)

    name = serializers.CharField(
        label='Name',
        read_only=False,
        help_text='The display name of the user',
        required=False,
        allow_blank=True,
        min_length=3,
        max_length=255,
    )
    avatar = serializers.URLField(
        label='Avatar',
        read_only=False,
        help_text='URL of the avatar to retrieve the file from',
        required=False,
        allow_blank=True,
    )
    description = serializers.CharField(
        label='Description',
        read_only=False,
        help_text='The description / bio of the user',
        required=False,
        allow_blank=True,
        max_length=500,
    )
    userType = serializers.ChoiceField(
        source='user_type',
        label='User Type',
        read_only=False,
        help_text='The user type (role)',
        required=False,
        allow_blank=False,
        choices=IgniteUser.USER_TYPES,
    )
    showAuthoringTooltips = serializers.BooleanField(
        source='show_authoring_tooltips',
        label='Show Authoring Tooltips',
        read_only=False,
        help_text='Flag whether to show authoring tooltips',
        required=False,
    )

    class Meta:
        fields = (
            'sessionId',
            'secureSessionId',

            # Oxygen update fields:
            'name',
            'avatar',

            # IgniteUser update fields:
            'description',
            'userType',
            'showAuthoringTooltips',
        )

    def validate_userType(self, value):
        request = self.context.get('request')
        # Validate that a child user can not be of type parent or teacher:
        if request.user.is_child and value in [IgniteUser.PARENT, IgniteUser.TEACHER]:
            raise serializers.ValidationError('Child user can not be of type teacher or parent.')
        return value
