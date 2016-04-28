from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.db.models import Q, Count, Prefetch

from rest_framework import status
from rest_framework import generics
from rest_framework import exceptions
from rest_framework.request import clone_request
from rest_framework.response import Response
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.exceptions import PermissionDenied

from rest_framework_bulk import BulkCreateAPIView, BulkUpdateAPIView, BulkDestroyAPIView

from .filters import ClassroomFilter, ClassroomStateFilter
from .permissions import ClassroomPermission, IsNotChildOrReadOnly, IsGuardianOrClassroomTeacher, ClassroomWriteOnlyPermission

from .mixins import (
    CacheRootObjectMixin,
    UseAuthenticatedSerializerMixin,
    ChoicesOnGet,
    DisableHttpMethodsMixin,
    EnrichSerializerContextMixin,
    UpdateWithCreateMixin,
    BulkUpdateWithCreateMixin,
    FilterAllowedMixin,
)

from ..serializers import (
    ProjectWithOrderSerializer,
    ProjectWithOrderAuthenticatedSerializer,

    ClassroomSerializer,
    ClassroomAuthenticatedSerializer,

    TeacherStudentSerializer,
    ClassroomStudentSerializer,

    ClassroomCodeGeneratorSerializer,
    ClassroomCodeInviteSerializer,
    ClassroomCodeSerializer,
)

from ..models import (
    Classroom,
    ClassroomState,
    Project,
    ProjectInClassroom,
    ChildGuardian,
)
from marketplace.models import Purchase

from .project_views import (
    ProjectList,
    ProjectDetail,
)

from ..emails import joined_classroom_email, invite_classroom_code

from ..serializers import querysets


# region Classrooms Views
class ClassroomViewMixin(CacheRootObjectMixin, EnrichSerializerContextMixin, UseAuthenticatedSerializerMixin, ChoicesOnGet):
    model = Classroom
    serializer_class = ClassroomSerializer
    authenticated_serializer_class = ClassroomAuthenticatedSerializer
    embed_choices = ('projects', 'projectsIds',)
    allowed_filter_include_children_classrooms = True
    allowed_filter_exclude_archived_classrooms = False

    def get_queryset(self):
        queryset = Classroom.objects.all()
        queryset = querysets.optimize_for_serializer_classroom(queryset, embed_list=self.embed_list, embed_user=self.embed_user, with_counters=True)
        q_filter = self.get_allowed_q_filter(
            include_children_classrooms=self.allowed_filter_include_children_classrooms,
            exclude_archived_classrooms=self.allowed_filter_exclude_archived_classrooms,
        )
        queryset = queryset.filter(q_filter)
        return queryset


class ClassroomList(FilterAllowedMixin, ClassroomViewMixin, generics.ListCreateAPIView):
    filter_class = ClassroomFilter
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated, IsNotChildOrReadOnly,)
    ordering = ('id',)
    ordering_fields = ('id', 'added', 'title',)
    search_fields = ('title', 'description')

    def get_queryset(self):
        # Set allowed filter params before getting queryset:
        if self.request.user and not self.request.user.is_anonymous():
            include_list = filter(None, self.request.QUERY_PARAMS.get('include', '').split(','))

            # Allowed filter include children classrooms:
            self.allowed_filter_include_children_classrooms = 'children' in include_list

            # Allowed filter exclude archived classrooms:
            # By default allowed exclude archived classrooms.
            self.allowed_filter_exclude_archived_classrooms = (
                'isArchived' not in self.request.QUERY_PARAMS and  #used in ClassroomFilter
                'archived' not in include_list
            )

            queryset = super(ClassroomList, self).get_queryset()
        else:
            # None logged-in users don't have access to any object.
            queryset = Classroom.objects.none()

        return queryset


class ClassroomDetail(FilterAllowedMixin, ClassroomViewMixin, generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = (TokenAuthentication,)
    permission_classes = (ClassroomPermission, IsNotChildOrReadOnly)

    def get_queryset(self):
        qs = super(ClassroomDetail, self).get_queryset()
        if self.request.user and not self.request.user.is_anonymous():
            q_filter = self.get_allowed_q_filter()
            return qs.filter(q_filter)
        else:
            return qs.none()

# endregion Classrooms Views


# region Projects in Classrooms
class ClassroomProjectViewMixin(CacheRootObjectMixin, EnrichSerializerContextMixin):
    through_model = ProjectInClassroom
    serializer_class = ProjectWithOrderSerializer
    authenticated_serializer_class = ProjectWithOrderAuthenticatedSerializer
    embed_choices = ('lessons', 'lessonsIds',)
    embed_user_related = ('state', 'enrolled',)

    def get_queryset(self):
        queryset = super(ClassroomProjectViewMixin, self).get_queryset()

        #queryset is already optimized, just adding order:
        queryset = querysets.optimize_for_serializer_project(queryset, default=False, with_order=True)

        #filter projects in classroom:
        classroom_pk = self.kwargs.get('classroom_pk')
        queryset = queryset.filter(classrooms__pk=classroom_pk)

        return queryset

    def dispatch(self, request, *args, **kwargs):
        # prepare kwargs relying on:
        if 'classroom_pk' in kwargs:
            try:
                classroom_pk = int(kwargs.get('classroom_pk', ''))
            except (ValueError, TypeError):
                classroom_pk = None
            kwargs['classroom_pk'] = classroom_pk

        return super(ClassroomProjectViewMixin, self).dispatch(request, *args, **kwargs)


class ClassroomProjectList(DisableHttpMethodsMixin, ClassroomProjectViewMixin, ProjectList):
    ordering = ('order',)
    search_fields = ('title', 'description', 'teacher_additional_resources')
    disable_http_methods = ['post']  #create
    permission_classes = ProjectList.permission_classes + (ClassroomPermission,)
    allowed_filter_exclude_non_searchable_projects = False


class ClassroomProjectDetail(DisableHttpMethodsMixin, ClassroomProjectViewMixin, ProjectDetail):
    disable_http_methods = ['patch']  #partial_update
    permission_classes = ProjectDetail.permission_classes + (ClassroomPermission,)

    #override PUT to add (or edit) project-in-classroom, DELETE to remove project-in-classroom (not creating or deleting a project object).
    def put(self, request, *args, **kwargs):
        #classroom can add any published project:
        qs_projects = Project.objects.filter(publish_mode=Project.PUBLISH_MODE_PUBLISHED)
        try:
            project_obj = qs_projects.get(pk=self.kwargs['pk'])
        except qs_projects.model.DoesNotExist:
            raise PermissionDenied(detail='Only published projects are allowed to be added to a classroom.')

        # If the project is locked.
        if project_obj.lock != Project.NO_LOCK:

            # If the user doesn't have a permission to teach this project.
            if not project_obj.can_teach(request.user):
                raise PermissionDenied(detail='You don\'t have permission to teach this project')

        #use serializer to validate project_obj object, and get project order:
        serializer = self.get_serializer(project_obj, data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        project_order = serializer.validated_data['order']

        # Create a new ProjectInClassroom for the classroom and the project in the URL
        # but only if there isn't a ProjectInClassroom already in the DB.
        projectinclassroom, created = ProjectInClassroom.objects.get_or_create(
            classroom_id=self.kwargs.get('classroom_pk'),
            project=project_obj,
            defaults={
                'order': project_order,
            }
        )

        #change the order of the project in case of update:
        if not created and projectinclassroom.order != project_order:
            projectinclassroom.order = project_order
            projectinclassroom.save()

        # Delegate the response to the retrieve method. The reason is that the
        # object we create (ClassroomState) is not the object we want to return
        # (User object)
        self.request = clone_request(request, 'GET')
        return self.retrieve(self.request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):

        #get project-in-classroom object:
        projectinclassroom = get_object_or_404(ProjectInClassroom, classroom_id=self.kwargs.get('classroom_pk'), project=self.kwargs['pk'])

        #remove project from the classroom:
        projectinclassroom.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)

# endregion Projects in Classrooms


# region Students in Classrooms
class ClassroomStudentViewMixin(CacheRootObjectMixin, ChoicesOnGet):
    model = get_user_model()
    serializer_class = ClassroomStudentSerializer
    permission_classes = (ClassroomPermission,)

    def get_queryset(self):
        classroom_pk = self.kwargs.get('classroom_pk')
        self._classroom_registrations_qs = Classroom.objects.get(pk=classroom_pk).registrations.all().select_related('user')

        qs = self.model.objects.all()

        qs = querysets.optimize_for_serializer_classroom_student(qs, with_student_status=True)

        #filter my students classrooms states with ClassroomsStateFilter:
        classrooms_registrations_filter = ClassroomStateFilter(data=self.request.QUERY_PARAMS, queryset=self._classroom_registrations_qs)
        classrooms_registrations_qs = classrooms_registrations_filter.filter()

        #filter students that have any of my classrooms states filtered:
        qs = qs.filter(classrooms_states__in=classrooms_registrations_qs)
        #Note: no need to .distinct this queryset, since (user, classroom) is unique for ClassroomState,
        #       and we get states for a specific classroom.
        return qs

    def get_serializer_context(self):
        #get default context:
        context = super(ClassroomStudentViewMixin, self).get_serializer_context()

        #add 'classroom' object to serializer context (ClassroomStudentSerializer relies on it):
        classroom_pk = self.kwargs.get('classroom_pk')
        classroom = get_object_or_404(Classroom, pk=classroom_pk)
        context['classroom'] = classroom

        return context

    def perform_destroy(self, instance):
        #use serializer.delete() to delete:
        serializer = self.get_serializer(instance)
        serializer.delete()

    def dispatch(self, request, *args, **kwargs):
        # prepare kwargs relying on:
        if 'classroom_pk' in kwargs:
            try:
                classroom_pk = int(kwargs.get('classroom_pk', ''))
            except (ValueError, TypeError):
                classroom_pk = None
            kwargs['classroom_pk'] = classroom_pk

        return super(ClassroomStudentViewMixin, self).dispatch(request, *args, **kwargs)


class ClassroomStudentsList(ClassroomStudentViewMixin, BulkUpdateWithCreateMixin, BulkCreateAPIView, BulkUpdateAPIView, BulkDestroyAPIView, generics.ListAPIView):
    post_allow_update = False

    def partial_bulk_update(self, request, *args, **kwargs):
        '''Don't allow bulk PATCH updates'''
        return self.http_method_not_allowed(request, *args, **kwargs)

    def bulk_destroy(self, request, *args, **kwargs):
        id_list = request.QUERY_PARAMS.get('idList', '')
        if id_list:
            #convert idList to list of numbers:
            id_list = [int(i) for i in filter(lambda x: unicode(x).isnumeric(), [x.strip() for x in id_list.split(',')])]
            #make queryset of objects to delete:
            qs = self.filter_queryset(self.get_queryset())
            qs = qs.filter(id__in=id_list)
            self.perform_bulk_destroy(qs)
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            return Response(status=status.HTTP_400_BAD_REQUEST)

class ClassroomStudentsDetail(DisableHttpMethodsMixin, ClassroomStudentViewMixin, UpdateWithCreateMixin, generics.RetrieveUpdateDestroyAPIView):
    permission_classes = (IsGuardianOrClassroomTeacher, ClassroomPermission)
    disable_operation_methods = ['partial_update',]  #PATCH

    def get_serializer_context(self):
        context = super(ClassroomStudentsDetail, self).get_serializer_context()

        #add 'user_pk' to serializer context (ClassroomStudentSerializer relies on it):
        try:
            user_pk = int(self.kwargs.get('pk', ''))
        except (ValueError, TypeError):
            user_pk = None
        context['user_pk'] = user_pk

        return context
# endregion Students in Classrooms


# region Invite Code generation for Classrooms
class ClassroomCodeDetail(ChoicesOnGet, generics.RetrieveAPIView):
    model = Classroom
    serializer_class = ClassroomCodeSerializer
    lookup_field = 'code'
    lookup_url_kwarg = 'classroom_code'
    permission_classes = (IsAuthenticatedOrReadOnly,)

    def get_queryset(self):
        return self.model.objects.all()

    def initial(self, request, *args, **kwargs):
        #upercase lookup_url_kwarg 'classroom_code' in kwargs:
        if self.lookup_url_kwarg in kwargs:
            kwargs[self.lookup_url_kwarg] = kwargs[self.lookup_url_kwarg].upper()
        return super(ClassroomCodeDetail, self).initial(request, *args, **kwargs)


class ClassroomCodeWriteViewMixin(CacheRootObjectMixin):
    model = Classroom
    permission_classes = (ClassroomWriteOnlyPermission,)
    queryset = model.objects.all()

    def get_object(self):
        #NOTE: Override .get_object() method to retrieve the classroom object from cache. Permissions were already checked via .has_permission().
        classroom_obj = self.get_cache_root_object(Classroom, 'pk', 'classroom_pk')
        return classroom_obj


class ClassroomCodeGeneratorDetail(ClassroomCodeWriteViewMixin, ChoicesOnGet, generics.RetrieveAPIView):
    serializer_class = ClassroomCodeGeneratorSerializer

    def post(self, request, *args, **kwargs):
        #get object (also checks permission_classes on it):
        classroom_obj = self.get_cache_root_object(Classroom, 'pk', 'classroom_pk')

        #generate new code and save:
        classroom_obj.code = classroom_obj.generate_code()
        classroom_obj.save()

        #output object with serializer:
        serializer = self.get_serializer(classroom_obj)
        return Response(serializer.data)

    def delete(self, request, *args, **kwargs):
        #get object (also checks permission_classes on it):
        classroom_obj = self.get_cache_root_object(Classroom, 'pk', 'classroom_pk')

        #remove code and save:
        classroom_obj.code = None
        classroom_obj.save()

        #output object with serializer:
        serializer = self.get_serializer(classroom_obj)
        return Response(serializer.data)


class ClassroomCodeInviteList(ClassroomCodeWriteViewMixin, generics.CreateAPIView):
    serializer_class = ClassroomCodeInviteSerializer

    def perform_save(self, serializer):
        #get object (also checks permission_classes on it):
        self.object = self.get_object()

        #check that classroom has code to send:
        if not self.object.code:
            raise exceptions.PermissionDenied(detail='Classroom has no code for join. Please generate new one first.')

        invite_classroom_code(
            classroom=self.object,
            invitees=serializer.validated_data.get('invitees', []),
            message=serializer.validated_data.get('message', None),
        )
            
    def perform_create(self, serializer):
        self.perform_save(serializer)
    def perform_update(self, serializer):
        self.perform_save(serializer)

    def create(self, request, *args, **kwargs):
        response = super(ClassroomCodeInviteList, self).create(request, *args, **kwargs)
        if response.status_code == 201:
            response.status_code = 202
        return response

# endregion Invite Code generation for Classrooms
