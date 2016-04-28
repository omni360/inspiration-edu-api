import copy

from rest_framework import generics
from rest_framework import exceptions
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from rest_framework_bulk import BulkCreateAPIView, BulkUpdateAPIView, BulkDestroyAPIView
# from utils_app.bulk_views import BulkCreateAPIView, BulkUpdateAPIView  #mirror used for debug

from django.db.models import Q, Count, Prefetch
from rest_framework import status
from rest_framework.response import Response
from utils_app.counter import ExtendQuerySetWithSubRelated

from .filters import LessonFilter
from .permissions import ProjectAndLessonPermission, IsNotChildOrReadOnly, LessonCopyPermission, ProjectAndLessonDraftPermission

from .mixins import (
    CacheRootObjectMixin,
    UseAuthenticatedSerializerMixin,
    FilterAllowedMixin,
    ChoicesOnGet,
    DisableHttpMethodsMixin,
    EnrichSerializerContextMixin,
    BulkUpdateWithCreateMixin,
)
from drafts.views import DraftViewMixin

from ..serializers import (
    LessonSerializer,
    LessonAuthenticatedSerializer
)

from ..models import (
    Lesson,
    LessonState,
    Project
)

from ..serializers import querysets


######################
##### BASE VIEWS #####
######################
class LessonViewMixin(CacheRootObjectMixin,
                      EnrichSerializerContextMixin,
                      FilterAllowedMixin,
                      ChoicesOnGet,):
    model = Lesson
    serializer_class = LessonSerializer
    embed_choices = ('steps', 'stepsIds', 'draft',)
    embed_user_related = ('state',)
    allowed_filter_exclude_non_searchable_projects = False
    queryset = Lesson.objects.all()

    def get_queryset_parent_filter_params(self):
        parent_filter_params = {}
        project_pk = self.kwargs.get('project_pk', None)
        if project_pk:
            parent_filter_params['project'] = project_pk
        return parent_filter_params

    def get_queryset(self):
        queryset = super(LessonViewMixin, self).get_queryset()
        queryset = querysets.optimize_for_serializer_lesson(queryset, embed_list=self.embed_list, embed_user=self.embed_user, with_counters=True)
        q_filter = self.get_allowed_q_filter(exclude_non_searchable_projects=self.allowed_filter_exclude_non_searchable_projects)
        parent_filter_params = self.get_queryset_parent_filter_params()
        queryset = queryset.filter(q_filter, **parent_filter_params)
        return queryset

    def dispatch(self, request, *args, **kwargs):
        # prepare kwargs relying on:
        if 'project_pk' in kwargs:
            try:
                project_pk = int(kwargs.get('project_pk', ''))
            except (ValueError, TypeError):
                project_pk = None
            kwargs['project_pk'] = project_pk

        return super(LessonViewMixin, self).dispatch(request, *args, **kwargs)

    def perform_create(self, serializer):
        self.perform_save(serializer)
    def perform_update(self, serializer):
        self.perform_save(serializer)
    def perform_save(self, serializer):
        '''
        Set the object's owner, based on the incoming request.
        '''
        project_pk = self.kwargs.get('project_pk', None)
        serializer.save(project_id=project_pk)

        # change the parent 'updated' field of the last instance changed:
        instance = None
        if serializer.instance:
            instance = serializer.instance if not isinstance(serializer.instance, type([])) else serializer.instance[-1]
        if instance:
            instance.change_parent_updated_field(instance.updated)

    def perform_destroy(self, instance, change_parent_updated=True):
        super(LessonViewMixin, self).perform_destroy(instance)

        # Remove lesson from its project.extra lessonsInit groups:
        project_extra = instance.project.extra or {}
        lessons_init = project_extra.get('lessonsInit', [])
        project_extra_is_changed = False
        for lessons_group in lessons_init:
            lessons_ids = lessons_group.get('lessonsIds', [])
            if instance.id in lessons_ids:
                lessons_ids.remove(instance.id)
                project_extra_is_changed = True
        if project_extra_is_changed:
            #Note: This should never fail here, since only removing lessons ids from lessonsInit groups (here just for robust).
            try:
                instance.project.extra = instance.project.validate_extra_field(project_extra)
            except ValueError:
                pass
            else:
                instance.project.save(update_fields=['extra'])

        # change the parent 'updated' field of the last instance changed:
        if change_parent_updated:
            instance.change_parent_updated_field()

    def perform_bulk_destroy(self, objects):
        num_objects = len(objects)
        for i, obj in enumerate(objects):
            self.perform_destroy(obj, change_parent_updated=(i==num_objects-1))
            
            
class LessonList(LessonViewMixin,
                 BulkUpdateWithCreateMixin,
                 BulkCreateAPIView,
                 BulkUpdateAPIView,
                 BulkDestroyAPIView,
                 generics.ListCreateAPIView):
    filter_class = LessonFilter
    permission_classes = (IsAuthenticatedOrReadOnly, IsNotChildOrReadOnly, ProjectAndLessonPermission,)
    search_fields = ('title',)

    def _copy_lessons_to_project(self, copy_from_lessons_ids):
        # Get lessons to copy and check permissions:
        disallowed_lessons_ids = []
        copy_lessons = []
        for copy_lesson_id in copy_from_lessons_ids:
            if not copy_lesson_id.isnumeric():
                raise exceptions.ParseError('Copy from lessons IDs must be list of integers only.')
            try:
                copy_lesson = Lesson.objects.get(id=copy_lesson_id)
            except Lesson.DoesNotExist:
                disallowed_lessons_ids.append(copy_lesson_id)
            else:
                # check that lesson is allowed to be copied:
                if not copy_lesson.project.is_editor(self.request.user):
                    disallowed_lessons_ids.append(copy_lesson_id)
                    continue
                # add lesson to copy list:
                copy_lessons.append(copy_lesson)

        # If some of the lessons are not allowed to be copied:
        if disallowed_lessons_ids:
            raise exceptions.ParseError(
                'Some of the lessons are not allowed to be copied [%s].' %
                ', '.join(disallowed_lessons_ids)
            )

        # Get the project to copy to (should not fail, since permission_classes validate this):
        project = Project.objects.get(pk=self.kwargs.get('project_pk'))

        # Copy the lessons:
        new_lessons = []
        copied_lessons_to_new_dict = {}  # gather all copied lessons to new lessons ids
        copied_projects_set = set()  # gather all projects copied from
        for copy_lesson in copy_lessons:
            new_lesson = copy_lesson.copy_lesson_to_project(project)
            new_lessons.append(new_lesson)
            copied_lessons_to_new_dict[copy_lesson.id] = new_lesson.id
            copied_projects_set.add(copy_lesson.project)

        # Set extra lessonsInit of new lessons in target project:
        new_lessons_init = []
        copied_projects_ids_processed = set()  # mark set of projects processed
        # Go over the copy lessons, and process its project:
        for copy_lesson in copy_lessons:
            if copy_lesson.project.id in copied_projects_ids_processed:
                continue
            copied_projects_ids_processed.add(copy_lesson.project.id)  # mark project as processed
            copy_extra = copy_lesson.project.extra or {}
            copy_lessons_init = copy_extra.get('lessonsInit', [])
            # Copy the lessons init groups of the lessons copied:
            for copy_lessons_group in copy_lessons_init:
                # Get the new lessons ids:
                new_lessons_group_ids = []
                for copy_lesson_id in copy_lessons_group['lessonsIds']:
                    if copy_lesson_id in copied_lessons_to_new_dict:
                        new_lessons_group_ids.append(copied_lessons_to_new_dict.pop(copy_lesson_id))
                # If got lessons ids in the group, then copy the group with the new lessons ids to the new lessons init list:
                if new_lessons_group_ids:
                    new_lessons_group = copy.deepcopy(copy_lessons_group)
                    new_lessons_group['lessonsIds'] = new_lessons_group_ids
                    new_lessons_init.append(new_lessons_group)
        # If got new lessons init groups, then append them to the project extra lessonsInit:
        if new_lessons_init:
            project.extra = project.extra or {}
            project.extra.setdefault('lessonsInit', [])
            project.extra['lessonsInit'] += new_lessons_init
            project.save(update_fields=['extra'], change_updated_field=False)

        # change the parent 'updated' field of the last instance changed:
        if new_lessons:
            instance = new_lessons[-1]
            instance.change_parent_updated_field(instance.updated)

        return new_lessons

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

    def create(self, request, *args, **kwargs):
        # Copy lessons to project:
        copy_from_lessons_ids_str = self.request.GET.get('copyFromLessonsIds', '')
        copy_from_lessons_ids = filter(None, [x.strip() for x in unicode(copy_from_lessons_ids_str).split(',')])
        if copy_from_lessons_ids:
            new_lessons = self._copy_lessons_to_project(copy_from_lessons_ids)
            serializer = self.get_serializer(instance=new_lessons, many=True)
            return Response(data=serializer.data, status=status.HTTP_201_CREATED)

        # Regular create:
        return super(LessonList, self).create(request, *args, **kwargs)


class LessonDetail(LessonViewMixin,
                   generics.RetrieveUpdateDestroyAPIView):
    permission_classes = (IsAuthenticatedOrReadOnly, ProjectAndLessonPermission,)


class LessonDraftList(DisableHttpMethodsMixin, DraftViewMixin, LessonList):
    permission_classes = (IsAuthenticatedOrReadOnly, IsNotChildOrReadOnly, ProjectAndLessonDraftPermission,)
    disable_http_methods = ['POST', 'DELETE']  #create, remove
    embed_list_base = ['origin']  #base embed allowed - origin
    embed_user_related = tuple()  #disable any user related embed
    view_draft_list = True  #flag for ProjectAndLessonPermission to determine view is draft list

    def get_queryset_parent_filter_params(self):
        parent_filter_params = super(LessonDraftList, self).get_queryset_parent_filter_params()
        parent_filter_params['draft_origin__project'] = parent_filter_params.pop('project')
        return parent_filter_params


class LessonDraftDetail(DraftViewMixin, LessonDetail):
    permission_classes = (IsAuthenticatedOrReadOnly, ProjectAndLessonDraftPermission,)
    lookup_url_kwarg = 'lesson_pk'


class LessonCopyDetail(LessonViewMixin,
                       generics.CreateAPIView):
    permission_classes = (IsAuthenticatedOrReadOnly, LessonCopyPermission)

    def create(self, request, *args, **kwargs):
        """
        This view allows only to create object by copying it from existing one
        We validate user permissions for both old lesson and new, create new lesson and then return it.
        """
        # check if the lesson is allowed to copy
        lesson_to_copy = get_object_or_404(Lesson.objects.all(), id=request.data.get('oldLessonId'))
        self.check_object_permissions(self.request, lesson_to_copy)
        # check if the project is allowed to edit
        to_project = get_object_or_404(Project.objects.all(), id=request.data.get('newProjectId'))
        self.check_object_permissions(self.request, to_project)
        # copy lesson and return
        new_lesson = lesson_to_copy.copy_lesson_to_project(to_project)
        new_lesson.change_parent_updated_field(new_lesson.updated)
        serializer = self.get_serializer(new_lesson)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class LessonListOnlyGet(DisableHttpMethodsMixin, LessonList):
    disable_operation_methods = ['create',]
    permission_classes = (IsAuthenticatedOrReadOnly, IsNotChildOrReadOnly,)
    allowed_filter_exclude_non_searchable_projects = True
    queryset = Lesson.objects.origins()


class LessonDetailOnlyGet(DisableHttpMethodsMixin, LessonDetail):
    disable_operation_methods = ['update', 'partial_update', 'destroy',]
    permission_classes = (IsAuthenticatedOrReadOnly, ProjectAndLessonPermission,)
    queryset = Lesson.objects.origins()
