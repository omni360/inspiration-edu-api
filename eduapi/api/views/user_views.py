import json
import requests
import copy
from requests.structures import CaseInsensitiveDict

from django.db.models import Q
from django.conf import settings
from django.http import JsonResponse
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError

from rest_framework import generics
from rest_framework.exceptions import ParseError, NotAuthenticated, APIException
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.authentication import TokenAuthentication
from rest_framework.request import clone_request
from rest_framework.response import Response
from rest_framework import status
from rest_framework.settings import api_settings

from rest_framework_bulk import BulkCreateAPIView, BulkUpdateAPIView, BulkDestroyAPIView

from ..auth.oxygen_operations import OxygenOperations
from ..auth.spark_drive_operations import SparkDriveOperations

from ..models import (
    IgniteUser,
    ChildGuardian,
    ClassroomState,
    ProjectState,
    LessonState,
    ProjectInClassroom,
    Classroom,
    Project,
    OwnerDelegate,
    Review,
)

from ..serializers import (
    FullUserSerializer,
    UserSerializer,
    SparkDriveUserUpdateSerializer,
    UserActivitySerializer,
    ChildOfGuardianSerializer,
    ChildOfCurrentUserSerializer,
    TeacherStudentSerializer,
    DelegateOfCurrentUserSerializer,
    DelegatorOfCurrentUserSerializer,
)

from .permissions import (
    OnlySelf,
    SelfOrTeacherReadOnly,
    GuardianOrReadOnly,
    UsersExtraInfoPermission,
)
from .mixins import (
    CacheRootObjectMixin,
    DisableHttpMethodsMixin,
    MappedOrderingView,
    FilterAllowedMixin,
)
from .filters import (
    ClassroomStateFilter,
    MyUserFilter,
    MyChildGuardianFilter,
)
from .state_views import (
    LessonStateList,
    ProjectStateList,
    ClassroomStateList,

    LessonStateDetail,
    ProjectStateDetail,
    ClassroomStateDetail,
)
from .review_views import (
    ReviewList,
    ReviewDetail,
)

from ..serializers import querysets


class CurrentUser(generics.RetrieveUpdateAPIView):
    '''
    Gets the currently logged in user's details.
    '''

    model = get_user_model()
    serializer_class = FullUserSerializer

    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return get_user_model().objects.all()
    def get_object(self):
        '''
        Get the current user
        '''

        # No need for this, because this inherently returns the correct object.
        # self.check_object_permissions(self.request, obj)

        return self.request.user

    def update(self, request, *args, **kwargs):
        """
        Update the details of the current user in the Spark Drive API,
        then update in our backend and return the result.
        """
        #get serializer data:
        serializer = SparkDriveUserUpdateSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)

        #get user:
        user = self.get_object()

        #update the user via Spark Drive:
        sparkdrive_user_data = {k:v for k,v in serializer.validated_data.items() if k in ['name', 'avatar']}
        if sparkdrive_user_data:
            errors = {}

            #validate we got both session id and secure session id:
            session_id = serializer.validated_data.get('sessionId')
            secure_session_id = serializer.validated_data.get('secureSessionId')
            if not session_id:
                errors['sessionId'] = ['This field is required to change data']
            if not secure_session_id:
                errors['secureSessionId'] = ['This field is required to change data']

            if not errors:
                #initialize Spark Drive API operations:
                sparkdrive_operations = SparkDriveOperations(
                    session_id=session_id,
                    secure_session_id=secure_session_id
                )

                avatar_file_url = sparkdrive_user_data.get('avatar', None)
                try:
                    sparkdrive_operations.update_user(user=user, data=sparkdrive_user_data)
                except SparkDriveOperations.SparkDriveApiError as exc:
                    # If invalid session and secure session:
                    if exc.spark_status_code == 401:
                        errors = {
                            api_settings.NON_FIELD_ERRORS_KEY: [
                                'SparkDrive API session is not valid. Please login again.',
                            ],
                        }
                    # Any other error (usually bad request):
                    else:
                        # Default error output:
                        errors = {
                            api_settings.NON_FIELD_ERRORS_KEY: [
                                'Unknown error occurred.',
                            ],
                        }

                        # Analyze error to output more specific error.
                        # If omitted avatar from serializer data, then problem with uploading avatar:
                        if avatar_file_url and not sparkdrive_user_data.has_key('avatar'):
                            errors = {
                                'avatar': [
                                    'Could not upload the avatar file.',
                                ],
                            }
                        else:
                            # Translate spark error codes to errors output:
                            # [See: http://docs.acgcs.apiary.io/#reference/members/member/update-a-member]
                            spark_update_member_error_codes = {
                                4001:   {'name': ['Member name is already taken.']},
                                40028:  {'name': ['The member name must not be empty']},
                                40029:  {'name': ['The name must be between 3 and 255 characters length.']},
                                40031:  {'avatar': ['The Avatar Id is invalid.']},
                            }
                            if exc.spark_error_code in spark_update_member_error_codes:
                                errors = spark_update_member_error_codes.get(exc.spark_error_code)

                    # Add spark drive status code and error message to errors output:
                    errors['_sparkdrive_status_code'] = exc.spark_status_code
                    errors['_sparkdrive_error_message'] = exc.message

            if errors:
                # Bad request response with errors:
                return Response(
                    data=errors,
                    status=status.HTTP_400_BAD_REQUEST,
                )

        #update the user only in our system:
        user_data = {k:v for k,v in serializer.validated_data.items() if k in ['description', 'user_type', 'show_authoring_tooltips',]}
        if user_data:
            for k, v in user_data.items():
                setattr(user, k, v)
            user.save()

        #after successful update, return result of request GET method:
        self.request = clone_request(request, 'GET')
        return self.retrieve(self.request, *args, **kwargs)


class UserDetail(generics.RetrieveDestroyAPIView):
    '''
    Gets a read only user instance.
    '''

    model = get_user_model()
    serializer_class = UserSerializer
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticatedOrReadOnly, GuardianOrReadOnly,)

    def get_queryset(self):
        return get_user_model().objects.all()

    def perform_destroy(self, instance):
        #if user is child, first try to delete the child user from Oxygen:
        if instance.is_child:
            oxygen_operations = OxygenOperations()
            try:
                oxygen_operations.delete_guardian_child(self.request.user, instance, False)
            except oxygen_operations.OxygenRequestFailed as exc:
                raise APIException(detail=getattr(exc, 'message', 'Error deleting child user from Oxygen.'))

        instance.delete()

class UserList(generics.ListAPIView):
    '''
    Gets a read only list of users.
    '''

    model = get_user_model()
    serializer_class = UserSerializer
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        '''
        Can search users only by exact name and can't get unapproved children.
        '''

        # Get filters from the query string.
        # White-list the accepted filters: 
        #   - Partial match for 4 letters and upwards.
        #   - Exact match for everything.
        filters = {
            k: v 
            for k,v in self.request.QUERY_PARAMS.items()
            if (
                (k in ['name', 'name__exact', 'name__iexact']) or
                (k in ['name__icontains', 'name__contains'] and len(v) >= 4)
            )
        }

        # If no name was provided.
        if len(filters.keys()) == 0:
            raise ParseError(detail='Can search only by exact name, or partial of 4+ characters')

        # Search by (i)exact name AND only approved children or adults.
        return self.model.objects.filter(
            Q(is_child=False) | Q(is_approved=True)
        ).filter(**filters)


# DEPRECATED!
# Note: Current state of this is not well optimized.
class UserActivity(DisableHttpMethodsMixin, UserDetail):
    model = get_user_model()
    queryset = get_user_model().objects.all()
    serializer_class = UserActivitySerializer
    permission_classes = (OnlySelf,)
    disable_operation_methods = ['update', 'partial_update', 'destroy']  #put, patch, delete

    def _get_view_queryset(self, view_class, user_field_qs, with_embed_list=None):
        #get the queryset from the view:
        view_instance = view_class(lookup_url_kwarg='user_pk')
        view_instance.args = self.args
        view_instance.kwargs = self.kwargs
        view_instance.request = clone_request(self.request, self.request.method)
        view_instance.queryset = user_field_qs
        view_instance.initial(view_instance.request, self.args, self.kwargs)
        if with_embed_list:
            view_instance.embed_list += with_embed_list
        return view_instance.filter_queryset(view_instance.get_queryset())

    def get_object(self):
        user_obj = super(UserActivity, self).get_object()

        user_obj.activity_reviews = self._get_view_queryset(ReviewList, user_obj.reviews.all())
        user_obj.activity_projects = self._get_view_queryset(ProjectStateList, user_obj.projects.all(), with_embed_list=['lessonStates'])
        user_obj.activity_classrooms = self._get_view_queryset(ClassroomStateList, user_obj.classrooms_states.all())

        return user_obj


class ChildrenViewMixin(object):
    serializer_class = ChildOfGuardianSerializer
    model = ChildGuardian
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        qs = self.model.objects.get_queryset()
        qs = qs.select_related('child')
        return qs

class ChildrenList(ChildrenViewMixin, MappedOrderingView, BulkCreateAPIView, generics.ListCreateAPIView):
    ordering_fields_map = {
        'id': None,
        'guardianId': None,
        'name': None,
        'shortName': None,
        'avatar': None,
        'joined': None,
        'moderatorType': None,
        'moderatedSince': None,
    }

    def create(self, request, *args, **kwargs):
        #force create as bulk list:
        bulk_data = request.data if isinstance(request.data, list) else [request.data]

        serializer = self.get_serializer(data=bulk_data, many=True)
        serializer.is_valid(raise_exception=True)
        self.perform_bulk_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ChildrenDetails(ChildrenViewMixin, generics.RetrieveAPIView):
    lookup_field = 'child_id'
    lookup_url_kwarg = 'child_pk'


class CurrentUserChildrenViewMixin(object):
    serializer_class = ChildOfCurrentUserSerializer

    def get_queryset(self):
        queryset = self.request.user.childguardian_child_set.all()
        queryset = queryset.select_related('child')
        return queryset


class CurrentUserChildrenList(CurrentUserChildrenViewMixin, ChildrenList):
    filter_class = MyChildGuardianFilter


class CurrentUserChildrenDetails(CurrentUserChildrenViewMixin, ChildrenDetails):
    pass


class CurrentUserStudentsViewMixin(object):
    model = get_user_model()
    serializer_class = TeacherStudentSerializer
    permission_classes = (IsAuthenticated,)

    queryset = get_user_model().objects.all()

    def get_queryset(self):
        qs = super(CurrentUserStudentsViewMixin, self).get_queryset()

        #filter my students classrooms states with ClassroomsStateFilter:
        my_students_classrooms_states_qs = ClassroomState.objects.filter(classroom__owner=self.request.user)
        my_students_classrooms_states_filter = ClassroomStateFilter(data=self.request.QUERY_PARAMS, queryset=my_students_classrooms_states_qs)
        self._my_students_classrooms_states_qs = my_students_classrooms_states_filter.filter()

        #optimieze queryset for serializer:
        qs = querysets.optimize_for_serializer_classroom_student(qs, student_classroom_states_queryset=self._my_students_classrooms_states_qs)

        #filter students that have any of my classrooms states filtered:
        qs = qs.filter(pk__in=self._my_students_classrooms_states_qs.values('user'))
        #for pagination, make sure to order the queryset:
        qs = qs.order_by('name')  #order by name

        # #order by -student_enroll_time (the min added time of the student classroom state) - using sub-related-queryset extension:
        # from utils_app.counter import ExtendQuerySetWithSubRelated
        # from django.db.models import Min
        # from django.utils import timezone
        # qs = ExtendQuerySetWithSubRelated(qs)
        # qs = qs.annotate_related('student_enroll_time', Min('added'), 'classrooms_states', self._my_students_classrooms_states_qs, timezone.now())
        # qs = qs.order_by('-student_enroll_time')

        #in case excluding using studentClassroom__ne, omit the whole student from the list even in case she is enrolled to another classroom:
        if self.request.QUERY_PARAMS.get('omitStudent') in ['1', 'true', 'yes']:
            omit_my_students_classrooms_states_qs = my_students_classrooms_states_filter.filter_specs_where(is_negated=True, flip_negation=True)
            qs = qs.exclude(classrooms_states__in=omit_my_students_classrooms_states_qs)

        return qs

    def get_serializer_context(self):
        context = super(CurrentUserStudentsViewMixin, self).get_serializer_context()
        context['teacher'] = self.request.user
        assert hasattr(self, '_my_students_classrooms_states_qs'), (
            'Serializer must be initialized after view .get_queryset() or .get_object() was called!'
        )
        context['students_classroom_states_qs'] = self._my_students_classrooms_states_qs
        return context


class CurrentUserStudentsList(CurrentUserStudentsViewMixin, BulkUpdateAPIView, generics.ListAPIView):
    filter_class = MyUserFilter

    def perform_create(self, serializer):
        self.perform_save(serializer)
    def perform_update(self, serializer):
        self.perform_save(serializer)
    def perform_save(self, serializer):
        #track old child students statuses:
        old_child_students_statuses = {}
        if serializer.instance:
            old_child_students_statuses = {
                child_student.id: {
                    student_classroom_state.classroom_id: student_classroom_state.status
                    for student_classroom_state in child_student.student_classrooms_states
                }
                for child_student in serializer.instance if child_student.is_child
            }

        objects = serializer.save()

        #TODO: move this operation to background with celery.
        #make dict map from oxygen_id to student for students that has classroom state status changed to 'approved':
        ox_approved_child_students = []
        for child_student in [student for student in objects if student.is_child]:
            for student_classroom_state in child_student.student_classrooms_states:
                old_student_classroom_status = old_child_students_statuses.get(child_student.id, {}).get(student_classroom_state.classroom_id)
                if student_classroom_state.status != old_student_classroom_status and student_classroom_state.status == ClassroomState.APPROVED_STATUS:
                    ox_approved_child_students.append(child_student)
                    continue
        #link child-guardian as educator in Oxygen system:
        if ox_approved_child_students:
            oxygen_operations = OxygenOperations()
            moderated_children = oxygen_operations.add_guardian_children(
                guardian=self.request.user,
                moderated_children={
                    ChildGuardian.MODERATOR_EDUCATOR: ox_approved_child_students,
                },
            )


class CurrentUserStudentsDetail(CurrentUserStudentsViewMixin, DisableHttpMethodsMixin, generics.RetrieveUpdateDestroyAPIView):
    lookup_url_kwarg = 'student_pk'
    disable_http_methods = ['delete',]  #disable only DELETE but allow PUT and PATCH for 'studentClassroomStates'

    def get_serializer_context(self):
        context = super(CurrentUserStudentsDetail, self).get_serializer_context()
        try:
            student_pk = int(self.kwargs.get('student_pk', ''))
        except (ValueError, TypeError):
            student_pk = None
        context['student_pk'] = student_pk
        return context


class CurrentUserUsersViewMixin(object):
    model = get_user_model()
    serializer_class = UserSerializer
    permission_classes = (IsAuthenticated,)

    queryset = get_user_model().objects.all()

    def get_queryset(self):
        qs = super(CurrentUserUsersViewMixin, self).get_queryset()

        #filter students and users:
        qs = get_user_model().objects.filter(
            Q(pk__in=ClassroomState.objects.filter(classroom__owner=self.request.user).values('user')) |  #students of the current user (of any status)
            Q(pk__in=ChildGuardian.objects.filter(guardian=self.request.user).values('child'))  #children of the current user
        )

        return qs

class CurrentUserUsersList(CurrentUserUsersViewMixin, generics.ListAPIView):
    filter_class = MyUserFilter


class CurrentUserUsersDetail(CurrentUserUsersViewMixin, generics.RetrieveAPIView):
    lookup_url_kwarg = 'user_pk'
    root_view_lookup_url_kwarg = 'user_pk'


class CurrentUserDelegateViewMixin(object):
    serializer_class = DelegateOfCurrentUserSerializer
    model = OwnerDelegate
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        queryset = self.request.user.ownerdelegate_delegate_set.all()
        queryset = queryset.select_related('user')
        return queryset

    def reset_owner_projects_locked_by_editors(self, delegator, delegates_ids):
        if not delegates_ids:
            return

        #update current_editor to None for projects (or projects drafts) of the delegator locked by those delegates:
        Project.objects.active_and_deleted().filter(
            Q(owner=delegator) | Q(draft_origin__owner=delegator),
            current_editor__in=delegates_ids,
        ).update(
            current_editor=None,
        )


class CurrentUserDelegateList(CurrentUserDelegateViewMixin, MappedOrderingView, BulkDestroyAPIView, generics.ListAPIView):
    # filter_class = MyChildGuardianFilter
    ordering_fields_map = {
        'id': None,
        'delegatorId': None,
        'name': None,
        'shortName': None,
        'avatar': None,
        'joined': None,
        'delegatedSince': None,
    }
    
    def create(self, request, *args, **kwargs):
        #force create as bulk list:
        bulk_data = request.data if isinstance(request.data, list) else [request.data]

        serializer = self.get_serializer(data=bulk_data, many=True)
        serializer.is_valid(raise_exception=True)
        self.perform_bulk_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_bulk_destroy(self, qs):
        editors_ids = list(qs.values_list('user_id', flat=True))
        super(CurrentUserDelegateList, self).perform_bulk_destroy(qs)
        self.reset_owner_projects_locked_by_editors(self.request.user, editors_ids)

    def bulk_destroy(self, request, *args, **kwargs):
        id_list = request.QUERY_PARAMS.get('idList', '')
        if id_list:
            #convert idList to list of numbers:
            id_list = [int(i) for i in filter(lambda x: unicode(x).isnumeric(), [x.strip() for x in id_list.split(',')])]
            #make queryset of objects to delete:
            qs = self.filter_queryset(self.get_queryset())
            qs = qs.filter(user_id__in=id_list)
            self.perform_bulk_destroy(qs)
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            return Response(status=status.HTTP_400_BAD_REQUEST)


class CurrentUserDelegateDetail(CurrentUserDelegateViewMixin, generics.RetrieveDestroyAPIView):
    lookup_field = 'user_id'
    lookup_url_kwarg = 'delegate_pk'

    def perform_destroy(self, instance):
        super(CurrentUserDelegateDetail, self).perform_destroy(instance)
        self.reset_owner_projects_locked_by_editors(instance.owner, [instance.user_id])


class CurrentUserDelegatorViewMixin(object):
    serializer_class = DelegatorOfCurrentUserSerializer
    model = OwnerDelegate
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        queryset = self.request.user.ownerdelegate_delegator_set.all()
        queryset = queryset.select_related('owner')
        return queryset

    def reset_editor_locked_projects_of_owners(self, delegate, delegators_ids):
        if not delegators_ids:
            return

        #update current_editor to None for projects (or projects drafts) of the owner locked by those delegates:
        Project.objects.active_and_deleted().filter(
            Q(owner__in=delegators_ids) | Q(draft_origin__owner__in=delegators_ids),
            current_editor=delegate,
        ).update(
            current_editor=None,
        )


class CurrentUserDelegatorList(CurrentUserDelegatorViewMixin, MappedOrderingView, BulkDestroyAPIView, generics.ListAPIView):
    # filter_class = MyChildGuardianFilter
    ordering_fields_map = {
        'id': None,
        'delegateId': None,
        'name': None,
        'shortName': None,
        'avatar': None,
        'joined': None,
        'delegatedSince': None,
    }

    def create(self, request, *args, **kwargs):
        #force create as bulk list:
        bulk_data = request.data if isinstance(request.data, list) else [request.data]

        serializer = self.get_serializer(data=bulk_data, many=True)
        serializer.is_valid(raise_exception=True)
        self.perform_bulk_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_bulk_destroy(self, qs):
        owners_ids = list(qs.values_list('owner_id', flat=True))
        super(CurrentUserDelegatorList, self).perform_bulk_destroy(qs)
        self.reset_editor_locked_projects_of_owners(self.request.user, owners_ids)

    def bulk_destroy(self, request, *args, **kwargs):
        id_list = request.QUERY_PARAMS.get('idList', '')
        if id_list:
            #convert idList to list of numbers:
            id_list = [int(i) for i in filter(lambda x: unicode(x).isnumeric(), [x.strip() for x in id_list.split(',')])]
            #make queryset of objects to delete:
            qs = self.filter_queryset(self.get_queryset())
            qs = qs.filter(owner_id__in=id_list)
            self.perform_bulk_destroy(qs)
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            return Response(status=status.HTTP_400_BAD_REQUEST)


class CurrentUserDelegatorDetail(CurrentUserDelegatorViewMixin, generics.RetrieveDestroyAPIView):
    lookup_field = 'owner_id'
    lookup_url_kwarg = 'delegator_pk'

    def perform_destroy(self, instance):
        self.reset_editor_locked_projects_of_owners(instance.user, [instance.owner_id])
        super(CurrentUserDelegatorDetail, self).perform_destroy(instance)


class UserLessonStateViewMixin(CacheRootObjectMixin, FilterAllowedMixin):
    permission_classes = (UsersExtraInfoPermission,)

    def get_queryset(self):
        qs = super(UserLessonStateViewMixin, self).get_queryset()

        # Filter states of the user:
        user_obj = self.get_cache_root_object(IgniteUser, 'pk', 'user_pk')
        q_filter_for_user = self.get_allowed_q_filter_for_user(LessonState, user_obj)
        qs = qs.filter(q_filter_for_user)

        return qs


class UserLessonStateDetail(DisableHttpMethodsMixin, CacheRootObjectMixin, LessonStateDetail):
    #allow only retrieve (GET) and destroy (DELETE):
    disable_operation_methods = ['create', 'update', 'partial_update',]


class UserProjectStateViewMixin(CacheRootObjectMixin, FilterAllowedMixin):
    permission_classes = (UsersExtraInfoPermission,)

    def get_queryset(self):
        qs = super(UserProjectStateViewMixin, self).get_queryset()

        # Filter states of the user:
        user_obj = self.get_cache_root_object(IgniteUser, 'pk', 'user_pk')
        q_filter_for_user = self.get_allowed_q_filter_for_user(ProjectState, user_obj)
        qs = qs.filter(q_filter_for_user)

        return qs


class UserProjectStateList(DisableHttpMethodsMixin, UserProjectStateViewMixin, ProjectStateList):
    #allow only retrieve (GET):
    disable_operation_methods = ['create', 'delete',]

class UserProjectStateDetail(DisableHttpMethodsMixin, UserProjectStateViewMixin, ProjectStateDetail):
    #allow only retrieve (GET) and destroy (DELETE):
    disable_operation_methods = ['create', 'update', 'partial_update',]


class UserProjectLessonStateViewMixin(UserLessonStateViewMixin):
    permission_classes = (UsersExtraInfoPermission,)

    def get_queryset(self):
        qs = super(UserProjectLessonStateViewMixin, self).get_queryset()

        # Filter states for project:
        qs = qs.filter(lesson__project=self.kwargs.get('project_pk'))

        return qs


class UserProjectLessonStateList(DisableHttpMethodsMixin, UserProjectLessonStateViewMixin, LessonStateList):
    #allow only retrieve (GET):
    disable_operation_methods = ['create', 'delete',]

class UserProjectLessonStateDetail(DisableHttpMethodsMixin, UserProjectLessonStateViewMixin, LessonStateDetail):
    #allow only retrieve (GET) and destroy (DELETE):
    disable_operation_methods = ['create', 'update', 'partial_update',]


class UserClassroomStateViewMixin(CacheRootObjectMixin, FilterAllowedMixin):
    permission_classes = (UsersExtraInfoPermission,)

    def get_queryset(self):
        qs = super(UserClassroomStateViewMixin, self).get_queryset()

        # Filter states of the user:
        user_obj = self.get_cache_root_object(IgniteUser, 'pk', 'user_pk')
        q_filter_for_user = self.get_allowed_q_filter_for_user(ClassroomState, user_obj)
        qs = qs.filter(q_filter_for_user)

        return qs


class UserClassroomStateList(DisableHttpMethodsMixin, UserClassroomStateViewMixin, ClassroomStateList):
    #allow only retrieve (GET):
    disable_operation_methods = ['create', 'delete',]

class UserClassroomStateDetail(DisableHttpMethodsMixin, UserClassroomStateViewMixin, ClassroomStateDetail):
    #allow only retrieve (GET) and destroy (DELETE):
    disable_operation_methods = ['create', 'update', 'partial_update',]


class UserClassroomProjectStateViewMixin(UserProjectStateViewMixin):
    def get_queryset(self):
        qs = super(UserClassroomProjectStateViewMixin, self).get_queryset()

        # Filter states for classroom:
        qs = qs.filter(project__classrooms=self.kwargs.get('classroom_pk'))

        return qs


class UserClassroomProjectStateList(DisableHttpMethodsMixin, UserClassroomProjectStateViewMixin, ProjectStateList):
    #allow only retrieve (GET):
    disable_operation_methods = ['create', 'delete',]

class UserClassroomProjectStateDetail(DisableHttpMethodsMixin, UserClassroomProjectStateViewMixin, ProjectStateDetail):
    #allow only retrieve (GET) and destroy (DELETE):
    disable_operation_methods = ['create', 'update', 'partial_update',]


class UserReviewViewMixin(CacheRootObjectMixin, FilterAllowedMixin):
    permission_classes = (UsersExtraInfoPermission,)

    def get_queryset(self):
        qs = super(UserReviewViewMixin, self).get_queryset()

        # Filter reviews of the user:
        user_obj = self.get_cache_root_object(IgniteUser, 'pk', 'user_pk')
        q_filter_for_user = self.get_allowed_q_filter_for_user(Review, user_obj)
        qs = qs.filter(q_filter_for_user)

        return qs


class UserReviewList(DisableHttpMethodsMixin, UserReviewViewMixin, ReviewList):
    #allow only retrieve (GET):
    disable_operation_methods = ['create', 'delete',]


class UserReviewDetail(DisableHttpMethodsMixin, UserReviewViewMixin, ReviewDetail):
    #allow only retrieve (GET) and destroy (DELETE):
    disable_operation_methods = ['create', 'update', 'partial_update',]
