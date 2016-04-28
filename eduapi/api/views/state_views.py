from django.db.models import Q
from rest_framework import generics
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework import exceptions

from .permissions import (
    ProjectAndLessonReadOnlyPermission,
    ClassroomReadOnlyPermission,
)
from ..models import (
    ProjectState,
    ClassroomState,
    LessonState,
)
from ..serializers import (
    ProjectStateSerializer,
    ClassroomStateSerializer,
    LessonStateSerializer,
)
from .mixins import (
    CacheRootObjectMixin,
    MappedOrderingView,
    DisableHttpMethodsMixin,
    UpdateWithCreateMixin,
    EnrichSerializerContextMixin,
)
from .filters import (
    ProjectStateFilter,
    ClassroomStateFilter,
)

from ..serializers import querysets


######################
##### BASE VIEWS #####
######################

class LessonStateViewMixin(object):
    model = LessonState
    serializer_class = LessonStateSerializer

    queryset = LessonState.objects.all()

    def get_queryset(self):
        queryset = super(LessonStateViewMixin, self).get_queryset()
        queryset = querysets.optimize_for_serializer_lesson_state(queryset, with_counters=True)
        return queryset

class LessonStateList(MappedOrderingView, LessonStateViewMixin, generics.ListAPIView):
    ordering_fields_map = {'enrolltime': None, 'updated': None,}

class LessonStateDetail(LessonStateViewMixin, generics.RetrieveUpdateDestroyAPIView):
    #filter lesson states list for get_object (change base class filter by default lookup 'pk'):
    lookup_field = 'lesson_id'
    lookup_url_kwarg = 'lesson_pk'


class ProjectStateViewMixin(EnrichSerializerContextMixin):
    model = ProjectState
    serializer_class = ProjectStateSerializer
    embed_choices = ('lessonStates',)

    queryset = ProjectState.objects.all()

    def get_queryset(self):
        queryset = super(ProjectStateViewMixin, self).get_queryset()
        queryset =querysets.optimize_for_serializer_project_state(queryset, embed_list=self.embed_list, with_counters=True)
        return queryset

class ProjectStateList(MappedOrderingView, ProjectStateViewMixin, generics.ListAPIView):
    filter_class = ProjectStateFilter
    ordering_fields_map = {'enrolltime': None, 'updated': None,}

class ProjectStateDetail(ProjectStateViewMixin, generics.RetrieveUpdateDestroyAPIView):
    #filter project states list for get_object (change base class filter by default lookup 'pk'):
    lookup_field = 'project_id'
    lookup_url_kwarg = 'project_pk'


class ClassroomStateViewMixin(EnrichSerializerContextMixin):
    model = ClassroomState
    serializer_class = ClassroomStateSerializer
    embed_choices = ['projectStates']

    queryset = ClassroomState.objects.all()

    def get_queryset(self):
        qs = super(ClassroomStateViewMixin, self).get_queryset()
        qs = querysets.optimize_for_serializer_classroom_state(qs, with_counters=True)
        return qs

class ClassroomStateList(MappedOrderingView, ClassroomStateViewMixin, generics.ListAPIView):
    ordering_fields_map = {'enrolltime': None, 'updated': None,}
    filter_class = ClassroomStateFilter

class ClassroomStateDetail(ClassroomStateViewMixin, generics.RetrieveUpdateDestroyAPIView):
    #filter classroom states list for get_object (change base class filter by default lookup 'pk'):
    lookup_field = 'classroom_id'
    lookup_url_kwarg = 'classroom_pk'



########################
##### NESTED VIEWS #####
########################

class CurrentUserStateMixin(object):
    authentication_classes = (TokenAuthentication,)

    def __init__(self, *args, **kwargs):
        super(CurrentUserStateMixin, self).__init__(*args, **kwargs)
        #make sure to copy the permission_classes before adding to it:
        self.permission_classes = tuple(self.permission_classes) + (IsAuthenticated,)

    def get_queryset(self):
        # strict registrations to current user states only:
        qs = super(CurrentUserStateMixin, self).get_queryset()
        if qs.model is LessonState:
            qs = qs.filter(project_state__user=self.request.user)
        else:
            qs = qs.filter(user=self.request.user)
        return qs


class CreateStateMixin(CacheRootObjectMixin, UpdateWithCreateMixin):
    create_state_permission_classes = tuple()
    state_subject_lookup_field = 'pk'
    state_subject_lookup_url_kwarg_pattern = '{}_pk'

    def __init__(self, *args, **kwargs):
        super(CreateStateMixin, self).__init__(*args, **kwargs)
        #make sure to copy the permission_classes before adding to it:
        self.permission_classes = tuple(self.permission_classes) + tuple(self.create_state_permission_classes)

    def get_serializer_context(self):
        context = super(CreateStateMixin, self).get_serializer_context()

        #get state subject and state subject object:
        state_subject = self.model.get_state_subject()
        state_subject_model = self.model._meta.get_field(state_subject).related_model
        state_subject_object = self.get_cache_root_object(state_subject_model, self.state_subject_lookup_field, self.state_subject_lookup_url_kwarg_pattern.format(state_subject), cache_root_name=state_subject)

        #put the root classroom object in the context:
        context[state_subject] = state_subject_object

        return context


class LessonLessonStateList(CurrentUserStateMixin, LessonStateList):
    pass

class LessonLessonStateDetail(CurrentUserStateMixin, CreateStateMixin, LessonStateDetail):
    create_state_permission_classes = (ProjectAndLessonReadOnlyPermission,)


class ProjectProjectStateList(CurrentUserStateMixin, ProjectStateList):
    pass

class ProjectProjectStateDetail(CurrentUserStateMixin, CreateStateMixin, ProjectStateDetail):
    create_state_permission_classes = (ProjectAndLessonReadOnlyPermission,)


class ClassroomClassroomStateList(CurrentUserStateMixin, ClassroomStateList):
    pass

class ClassroomClassroomStateDetail(DisableHttpMethodsMixin, CurrentUserStateMixin, ClassroomStateDetail):
    #Note: Do not allow CreateStateMixin in classroom state. Students are added with PUT to classroom-students-detail view.
    disable_operation_methods = ['update', 'partial_update', 'destroy']  #PUT, PATCH, DELETE


class ProjectLessonStateViewMixin(CurrentUserStateMixin):
    def get_queryset(self):
        qs = super(ProjectLessonStateViewMixin, self).get_queryset()
        qs = qs.filter(lesson__project=self.kwargs.get('project_pk'))
        return qs


class ProjectLessonStateList(ProjectLessonStateViewMixin, LessonLessonStateList):
    pass

class ProjectLessonStateDetail(ProjectLessonStateViewMixin, LessonLessonStateDetail):
    pass


class ClassroomProjectStateViewMixin(CurrentUserStateMixin):
    def get_queryset(self):
        qs = super(ClassroomProjectStateViewMixin, self).get_queryset()
        qs = qs.filter(project__classrooms=self.kwargs.get('classroom_pk'))
        return qs

class ClassroomProjectStateList(ClassroomProjectStateViewMixin, ProjectProjectStateList):
    pass

class ClassroomProjectStateDetail(ClassroomProjectStateViewMixin, ProjectProjectStateDetail):
    create_state_permission_classes = (ClassroomReadOnlyPermission, ProjectAndLessonReadOnlyPermission,)


class ClassroomCodeStateDetail(DisableHttpMethodsMixin, CurrentUserStateMixin, CreateStateMixin, ClassroomStateDetail):
    lookup_field = 'classroom__code'
    lookup_url_kwarg = 'classroom_code'
    disable_operation_methods = ['partial_update',]
    create_state_permission_classes = tuple()
    state_subject_lookup_field = 'code'
    state_subject_lookup_url_kwarg_pattern = '{}_code'
