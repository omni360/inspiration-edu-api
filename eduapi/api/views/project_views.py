from django.db.models import Prefetch, Count, Q

from rest_framework import generics
from rest_framework import exceptions
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from api.search_indexes.queries import get_searched_projects_ids, get_projects_ids_searched_by_lesson_titles, get_projects_ids_searched_by_title_tags_author

from utils_app.counter import ExtendQuerySetWithSubRelated

from .filters import ProjectFilter, ProjectStateFilter
from .permissions import (
    ProjectAndLessonPermission,
    IsNotChildOrReadOnly,
    ProjectLessonEditPermission,
    ProjectModePermission,
    ProjectEditLock,
    ProjectAndLessonDraftPermission,
    ProjectDraftEditLock,
    ProjectDraftModePermission,
)

from .mixins import (
    RootViewBuilder,
    CacheRootObjectMixin,
    UseAuthenticatedSerializerMixin,
    FilterAllowedMixin,
    ChoicesOnGet,
    EnrichSerializerContextMixin,
    MappedOrderingView,
    UpdateWithCreateMixin,
)
from drafts.views import DraftViewMixin

from ..serializers import (
    LessonSerializer,
    LessonAuthenticatedSerializer,

    ProjectSerializer,
    ProjectModeSerializer,
    # ProjectAuthenticatedSerializer,
)

from ..models import (
    Project,
    ProjectState,
    Lesson,
    LessonState,
)

from marketplace.models import Purchase

from .lesson_views import (
    LessonList,
    LessonDetail,
)

from ..serializers import querysets


######################
##### BASE VIEWS #####
######################

class ProjectViewMixin(CacheRootObjectMixin,
                       EnrichSerializerContextMixin,
                       FilterAllowedMixin,
                       ChoicesOnGet,):
    model = Project
    serializer_class = ProjectSerializer
    embed_choices = ('lessons', 'lessonsIds', 'draft',)
    embed_user_related = ('state', 'enrolled',)
    allowed_filter_exclude_non_searchable_projects = False

    def get_queryset(self):
        queryset = Project.objects.all()
        queryset = querysets.optimize_for_serializer_project(queryset, user=self.request.user, embed_list=self.embed_list, embed_user=self.embed_user, with_counters=True, with_permissions=True)
        q_filter = self.get_allowed_q_filter(exclude_non_searchable_projects=self.allowed_filter_exclude_non_searchable_projects)
        queryset = queryset.filter(q_filter)
        return queryset


class ProjectList(ProjectViewMixin,
                  MappedOrderingView,
                  generics.ListCreateAPIView):
    filter_class = ProjectFilter
    permission_classes = (IsNotChildOrReadOnly, ProjectAndLessonPermission,)
    ordering = ('id',)
    ordering_fields_map = {
        'id': None,
        'added': None,
        'updated' : None,
        'publishDate': None,
        'title': None,
        'duration': None,
        'age': None,
        'difficulty': None,
        'license': None,
    }
    # search_fields = ('title', 'description', 'teacher_info')
    allowed_filter_exclude_non_searchable_projects = True

    def get_queryset(self):
        ### Technical Note: Do not do prefetch_related inside Prefetch queryset, since django will execute the query
        ###     twice, ut do all the prefetch related in a single level.
        ###     But you can do select_related and annotate inside Prefetch queryset.

        queryset = super(ProjectList, self).get_queryset()

        # isPurchased filter
        isPurchased = self.request.QUERY_PARAMS.get('isPurchased')
        if isPurchased: # if exists
            isPurchased = isPurchased.lower() not in ['0', 'false']

            # When filtering in the same filter statement, Django checks that the
            # same "Purchase" has the user and the right permission.
            # On exclude it's different, so we use a different technique.
            # See: https://docs.djangoproject.com/en/1.8/topics/db/queries/#spanning-multi-valued-relationships
            if isPurchased: # is True or False
                queryset = queryset.filter(
                    purchases__user=self.request.user, 
                    purchases__permission=Purchase.TEACH_PERM
                )
            else:
                queryset = queryset.exclude(purchases=Purchase.objects.filter(
                    user=self.request.user,
                    permission=Purchase.TEACH_PERM,
                ))

        # forCollaboration filter
        forCollaboration = self.request.QUERY_PARAMS.get('forCollaboration')
        if forCollaboration:
            forCollaboration = forCollaboration.lower() not in ['0', 'false']

            # Get list of projects that that the user is the owner or delegate of the owner (projects for collaboration):
            if forCollaboration:
                if self.request.user.is_authenticated():
                    queryset = queryset.filter(
                        Q(owner=self.request.user) |  # owner
                        Q(owner__in=self.request.user.delegators.all())  # delegate of owner
                    )
                else:
                    # Annonymous user is not part of collaboration
                    queryset = queryset.none()

        enrolled_param = self.request.QUERY_PARAMS.get('enrolled')
        if enrolled_param:
            # Normalize the filter's value to True/False
            is_enrolled = enrolled_param.lower() not in ['0', 'false',]

            #projectstates projects queryset of the current user, or none if no current user:
            if self.request.user and not self.request.user.is_anonymous():
                projectstate_projects_qs = ProjectState.objects.filter(
                    user=self.request.user
                ).values('project')
            else:
                projectstate_projects_qs = ProjectState.objects.none()

            if is_enrolled:
                #filter projectstate projects further more using its own filter:
                projectstate_projects_filter = ProjectStateFilter(data=self.request.QUERY_PARAMS, queryset=projectstate_projects_qs)
                projectstate_projects_qs = projectstate_projects_filter.filter()
                #get only projects that has projectstates:
                queryset = queryset.filter(pk__in=projectstate_projects_qs)
            else:
                #get only projects that has not projectstates:
                queryset = queryset.exclude(pk__in=projectstate_projects_qs)

        # Search with indexing engine
        project_search_query = self.request.QUERY_PARAMS.get('q', False)
        if project_search_query:
            searchTagsAuthor = self.request.QUERY_PARAMS.get('searchTagsAuthor', False)
            if searchTagsAuthor:
                search_ids = get_projects_ids_searched_by_title_tags_author(project_search_query)
            else:
                search_ids = list(get_searched_projects_ids(project_search_query))
                # Search with indexing engine by lesson titles
                searchInLesson = self.request.QUERY_PARAMS.get('searchInLesson', False)
                if searchInLesson:
                    search_ids += list(get_projects_ids_searched_by_lesson_titles(project_search_query))
            queryset = queryset.filter(id__in=search_ids)

        return queryset


class ProjectDetail(ProjectViewMixin,
                    generics.RetrieveUpdateDestroyAPIView):
    
    permission_classes = (IsNotChildOrReadOnly, ProjectAndLessonPermission,)


class ProjectModeDetail(ProjectViewMixin,
                        generics.RetrieveUpdateAPIView):
    serializer_class = ProjectModeSerializer
    lookup_url_kwarg = 'project_pk'
    permission_classes = (IsAuthenticatedOrReadOnly, ProjectModePermission, ProjectEditLock)


class ProjectDraftDetail(DraftViewMixin,
                         ProjectDetail):
    permission_classes = (IsNotChildOrReadOnly, ProjectAndLessonDraftPermission,)
    lookup_url_kwarg = 'project_pk'


class ProjectDraftModeDetail(ProjectModeDetail):
    permission_classes = (IsAuthenticatedOrReadOnly, ProjectDraftModePermission, ProjectDraftEditLock)

    def get_object(self):
        obj = super(ProjectDraftModeDetail, self).get_object()

        # Check that object has draft:
        if not obj.has_draft:
            raise exceptions.NotFound

        return obj

    def get_serializer(self, *args, **kwargs):
        kwargs['use_draft_instance'] = True
        serializer = super(ProjectDraftModeDetail, self).get_serializer(*args, **kwargs)
        return serializer


########################
##### NESTED VIEWS #####
########################

class ProjectLessonViewMixin(object):

    def perform_create(self, serializer):
        
        #if create, set the project of the lesson to be the root project object:
        #Note: permission is already checked in permission classes (ProjectLessonEditPermission).
        self.serializer(project=self.get_root_object_project_edit())

    def perform_destroy(self, instance):
        #get root project for edit, and then use self.root_object_project_edit:
        root_object_project = self.get_root_object_project_edit()  #will throw exception if not permitted

        super(ProjectLessonViewMixin, self).perform_destroy(instance)


class ProjectLessonList(ProjectLessonViewMixin, RootViewBuilder, LessonList):
    serializer_class = LessonSerializer
    authenticated_serializer_class = LessonAuthenticatedSerializer
    ordering = ('order',)
    search_fields = ('title', 'description', 'teacher_additional_resources')
    permission_classes = LessonList.permission_classes + (ProjectLessonEditPermission,)

    root_view_name = 'project'
    root_view_class = ProjectDetail
    root_view_lookup_url_kwarg = 'project_pk'
    root_view_objects = {
        'project_edit': {'request_method': 'PUT'},
    }
    def make_root_queryset(self, root_object):
        root_qs = root_object.lessons.all()
        root_qs = root_qs.prefetch_related('registrations')
        return root_qs


class ProjectLessonDetail(ProjectLessonViewMixin, RootViewBuilder, LessonDetail):
    serializer_class = LessonSerializer
    authenticated_serializer_class = LessonAuthenticatedSerializer
    permission_classes = LessonDetail.permission_classes + (ProjectLessonEditPermission,)

    root_view_name = 'project'
    root_view_class = ProjectDetail
    root_view_lookup_url_kwarg = 'project_pk'
    root_view_objects = {
        'project_edit': {'request_method': 'PUT'},
    }
    def make_root_queryset(self, root_object):
        root_qs = root_object.lessons.all()
        return root_qs
