from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from rest_framework_bulk import BulkCreateAPIView, BulkUpdateAPIView, BulkDestroyAPIView

from .mixins import EnrichSerializerContextMixin, FilterAllowedMixin, CacheRootObjectMixin, BulkUpdateWithCreateMixin, DisableHttpMethodsMixin
from .permissions import IsNotChildOrReadOnly, ProjectAndLessonPermission, ProjectAndLessonDraftPermission
from ..serializers import StepSerializer
from ..models import Step
from drafts.views import DraftViewMixin


######################
##### BASE VIEWS #####
######################

class LessonStepViewMixin(EnrichSerializerContextMixin, FilterAllowedMixin, CacheRootObjectMixin):
    model = Step
    serializer_class = StepSerializer
    permission_classes = (
        IsNotChildOrReadOnly,
        ProjectAndLessonPermission,
    )
    embed_choices = ('draft',)
    queryset = Step.objects.all()

    def get_queryset_parent_filter_params(self):
        parent_filter_params = {}
        project_pk = self.kwargs.get('project_pk', None)
        lesson_pk = self.kwargs.get('lesson_pk', None)
        parent_filter_params['lesson'] = lesson_pk
        if project_pk:
            parent_filter_params['lesson__project'] = project_pk
        return parent_filter_params

    def get_queryset(self):
        queryset = super(LessonStepViewMixin, self).get_queryset()
        q_filter = self.get_allowed_q_filter()
        parent_filter_params = self.get_queryset_parent_filter_params()
        queryset = queryset.filter(q_filter, **parent_filter_params)
        queryset = queryset.select_related('lesson')
        return queryset

    def dispatch(self, request, *args, **kwargs):
        # prepare kwargs relying on:
        if 'project_pk' in kwargs:
            try:
                project_pk = int(kwargs.get('project_pk', ''))
            except (ValueError, TypeError):
                project_pk = None
            kwargs['project_pk'] = project_pk
        if 'lesson_pk' in kwargs:
            try:
                lesson_pk = int(kwargs.get('lesson_pk', ''))
            except (ValueError, TypeError):
                lesson_pk = None
            kwargs['lesson_pk'] = lesson_pk

        return super(LessonStepViewMixin, self).dispatch(request, *args, **kwargs)

    def perform_create(self, serializer):
        self.perform_save(serializer)
    def perform_update(self, serializer):
        self.perform_save(serializer)
    def perform_save(self, serializer):
        #relying on permissions that have already checked the 'lesson_pk' for the current user, can safely set lesson_id attribute:
        serializer.save(lesson_id=self.kwargs.get('lesson_pk', None))

        # change the parent 'updated' field of the last instance changed:
        instance = None
        if serializer.instance:
            instance = serializer.instance if not isinstance(serializer.instance, type([])) else serializer.instance[-1]
        if instance:
            instance.change_parent_updated_field(instance.updated)

    def perform_destroy(self, instance, change_parent_updated=True):
        instance.delete()

        # change the parent 'updated' field of the last instance changed:
        if change_parent_updated:
            instance.change_parent_updated_field()

    def perform_bulk_destroy(self, objects):
        num_objects = len(objects)
        for i, obj in enumerate(objects):
            self.perform_destroy(obj, change_parent_updated=(i==num_objects-1))


class ProjectLessonStepList(LessonStepViewMixin, BulkUpdateWithCreateMixin, BulkCreateAPIView, BulkUpdateAPIView, BulkDestroyAPIView, generics.ListAPIView):
    paginate_by = 50 # For steps allow up to 50 in a single page.
    post_allow_update = True

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


class ProjectLessonStepDetail(LessonStepViewMixin, generics.RetrieveUpdateDestroyAPIView):
    lookup_field = 'order'


class ProjectLessonStepDraftList(DisableHttpMethodsMixin, DraftViewMixin, ProjectLessonStepList):
    permission_classes = (IsNotChildOrReadOnly, ProjectAndLessonPermission,)
    disable_http_methods = ['POST', 'DELETE']  #create, remove
    embed_list_base = ['origin']  #base embed allowed - origin
    embed_user_related = tuple()  #disable any user related embed
    view_draft_list = True  #flag for ProjectAndLessonPermission to determine view is draft list

    def get_queryset_parent_filter_params(self):
        parent_filter_params = super(ProjectLessonStepDraftList, self).get_queryset_parent_filter_params()
        parent_filter_params['draft_origin__lesson'] = parent_filter_params.pop('lesson')
        if 'lesson__project' in parent_filter_params:
            parent_filter_params['draft_origin__lesson__project'] = parent_filter_params.pop('lesson__project')
        return parent_filter_params



class ProjectLessonStepDraftDetail(DraftViewMixin, ProjectLessonStepDetail):
    permission_classes = (IsNotChildOrReadOnly, ProjectAndLessonDraftPermission,)
