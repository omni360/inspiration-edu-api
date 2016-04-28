import datetime
from haystack import indexes

from api.models import Project, Lesson, IgniteUser


class ProjectIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True)
    tags = indexes.MultiValueField(model_attr='tags')  # Note: can be faceted to get tags counters
    title = indexes.CharField(model_attr='title')
    description = indexes.CharField(model_attr='description')
    owner_name = indexes.CharField(model_attr='owner__name')  # Note: can be faceted to get owners counters
    teacher_additional_resources = indexes.CharField(model_attr='teacher_additional_resources')
    updated = indexes.DateTimeField(model_attr='updated')

    # settings
    _tags_model_field = Project._meta.get_field_by_name('tags')[0]

    def get_model(self):
        return Project

    def index_queryset(self, using=None):
        """Used when the entire index for model is updated."""
        return self.get_model().objects.filter(
            updated__lte=datetime.datetime.now()
        ).select_related(
            'owner'
        )

    def prepare_tags(self, obj):
        value = self._tags_model_field.get_tags_list(obj.tags)
        return value

    def update_owner_projects(self, owner, using=None):
        # get all projects of the owner for updating index:
        index_queryset = self.get_model().objects.filter(
            owner=owner
        ).select_related(
            'owner'
        )

        backend = self._get_backend(using)
        if backend is not None:
            backend.update(self, index_queryset)


class LessonIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True)
    title = indexes.CharField(model_attr='title')
    updated = indexes.DateTimeField(model_attr='updated')
    project_id = indexes.IntegerField(model_attr='project_id')

    def get_model(self):
        return Lesson

    def index_queryset(self, using=None):
        """Used when the entire index for model is updated."""
        return self.get_model().objects.filter(updated__lte=datetime.datetime.now())
