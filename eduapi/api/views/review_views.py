from django.contrib.contenttypes.models import ContentType

from rest_framework import generics
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from .permissions import ProjectAndLessonPermission, ProjectAndLessonReadOnlyPermission, IsNotChildOrReadOnly, ReviewEditByOwnerOrGuardianOnly
from .mixins import CacheRootObjectMixin, ChoicesOnGet, FilterAllowedMixin, DisableHttpMethodsMixin

from ..serializers import ReviewSerializer
from ..models import Review, Lesson, Project

from ..serializers import querysets


######################
##### BASE VIEWS #####
######################

class ReviewViewMixin(FilterAllowedMixin,
                      ChoicesOnGet):
    model = Review
    serializer_class = ReviewSerializer

    def get_queryset(self):
        qs = Review.objects.all()
        qs = querysets.optimize_for_serializer_review(qs)
        return qs


class ReviewList(ReviewViewMixin, generics.ListCreateAPIView):
    permission_classes = (IsAuthenticatedOrReadOnly,)
    ordering = ('added',)


class ReviewDetail(ReviewViewMixin, generics.RetrieveUpdateDestroyAPIView):
    permission_classes = (IsAuthenticatedOrReadOnly, ReviewEditByOwnerOrGuardianOnly,)



########################
##### NESTED VIEWS #####
########################

# Project Reviews
################

class ProjectReviewViewMixin(CacheRootObjectMixin, ChoicesOnGet):
    permission_classes = (ProjectAndLessonReadOnlyPermission, IsAuthenticatedOrReadOnly, ReviewEditByOwnerOrGuardianOnly,)

    def get_queryset(self):
        qs = super(ProjectReviewViewMixin, self).get_queryset()
        project_content_type = ContentType.objects.get_for_model(Project)
        project_pk = self.kwargs.get('project_pk')
        qs = qs.filter(content_type=project_content_type, object_id=project_pk)
        return qs

    def dispatch(self, request, *args, **kwargs):
        # prepare kwargs relying on:
        if 'project_pk' in kwargs:
            try:
                project_pk = int(kwargs.get('project_pk', ''))
            except (ValueError, TypeError):
                project_pk = None
            kwargs['project_pk'] = project_pk

        return super(ProjectReviewViewMixin, self).dispatch(request, *args, **kwargs)

    def perform_create(self, serializer):
        self.perform_save(serializer)
    def perform_update(self, serializer):
        self.perform_save(serializer)

    def perform_save(self, serializer):
        ''' Associate the item with the relevant project before it's saved '''
        root_project = self.get_cache_root_object(Project, 'pk', 'project_pk')
        return serializer.save(
            owner=self.request.user,
            content_object=root_project,
        )


class ProjectReviewList(DisableHttpMethodsMixin, ProjectReviewViewMixin, ReviewList):
    disable_operation_methods = ['update',]

class ProjectReviewDetail(DisableHttpMethodsMixin, ProjectReviewViewMixin, ReviewDetail):
    disable_operation_methods = ['update',]

