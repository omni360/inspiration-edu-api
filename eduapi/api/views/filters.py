from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q, Case, When, Value, IntegerField
from django.contrib.auth import get_user_model

from rest_framework import filters, exceptions

from url_filter.filtersets import FilterSet, ModelFilterSet, StrictMode
from url_filter.filters import Filter, FilterSpec
from url_filter.backends.django import DjangoFilterBackend, LOOKUP_SEP

from api.search_indexes.queries import get_projects_ids_searched_by_exact_tags

from ..models import (
    Project,
    Lesson,
    Classroom,
    ClassroomState,
    ProjectState,
    ChildGuardian,
    Notification,
)


class IgniteFilterBackend(DjangoFilterBackend):
    def filter(self):
        # get the tags spec, and remove it from the specs list:
        spec_tags = None
        for spec in self.specs:
            if getattr(spec, 'is_tags_filter', None):
                spec_tags = spec
                self.specs.remove(spec)

        # regularly filter the queryset:
        qs = super(IgniteFilterBackend, self).filter()

        # handle the tags filter alone:
        if spec_tags:
            if not len(spec_tags.value):  #if value is empty list (not None)
                return qs.none()
            search_ids = get_projects_ids_searched_by_exact_tags(spec_tags.value)
            qs = qs.filter(id__in=search_ids)

        # handle ordering for filtering with order:
        for spec in self.includes:
            if getattr(spec, 'with_order', None):
                q_field = LOOKUP_SEP.join(spec.components)
                # Note that Case is supported by django 1.8 and above.
                qs = qs.annotate(
                    _filter_custom_order=Case(
                        *(
                            When(condition=Q(**{q_field: v}), then=Value(i)) for i,v in enumerate(spec.value)
                        ),
                        **{
                            'default': Value(len(spec.value)),
                            'output_field': IntegerField()
                        }
                    )
                ).order_by('_filter_custom_order')

        # print qs.query
        return qs


class IgniteFilterSet(FilterSet):
    filter_backend_class = IgniteFilterBackend

    def __init__(self, *args, **kwargs):
        # Use strict mode fail by default:
        kwargs.setdefault('strict_mode', StrictMode.fail)
        super(IgniteFilterSet, self).__init__(*args, **kwargs)

    def get_specs(self):
        """
        Returns specs. If raised ValidationError exception, then converts it to DRF ValidationError exception.
        """
        try:
            specs = super(IgniteFilterSet, self).get_specs()
        except ValidationError as exc:
            # Throw DRF ValidationError:
            raise exceptions.ValidationError({
                'filterErrors': exc.message_dict,
            })
        return specs

    def filter_specs(self, specs):
        """
        Bind specs to backend filter and return filtered queryset.
        """
        self.filter_backend.bind(specs)
        return self.filter_backend.filter()

    def filter_specs_where(self, is_negated=None, flip_negation=False):
        """
        By default takes all specs, binds to backend filter and returns the filtered queryset.
        If is_negated is set, then takes only the specs that are negated or not negated.
        If flip_negation is set, then flips the negation of each spec.
        """
        # Prepare specs (filter only specs with desired is_negated, and flip negation of each spec):
        specs = []
        for spec in self.get_specs():
            if is_negated is None or spec.is_negated == is_negated:
                specs.append(spec)
                if flip_negation:
                    spec.is_negated = not spec.is_negated
        return self.filter_specs(specs)

class IgniteModelFilterSet(IgniteFilterSet, ModelFilterSet):
    pass


class FilterWithOrder(Filter):
    lookups_with_order = ['in',]

    def __init__(self, *args, **kwargs):
        self.with_order = kwargs.pop('with_order', True)
        super(FilterWithOrder, self).__init__(*args, **kwargs)

    def get_spec(self, config):
        spec = super(FilterWithOrder, self).get_spec(config)
        if spec.lookup in self.lookups_with_order:
            spec.with_order = self.with_order
        return spec


class TagsFilter(Filter):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('lookups', ['in'])
        kwargs.setdefault('default_lookup', 'in')
        kwargs.setdefault('form_field', forms.CharField())
        super(TagsFilter, self).__init__(*args, **kwargs)

    def get_spec(self, config):
        spec = super(TagsFilter, self).get_spec(config)
        spec.is_tags_filter = True
        return spec


class AuthorFilter(IgniteModelFilterSet):
    id = Filter(source='id', form_field=forms.IntegerField(min_value=0), is_default=True)

    class Meta:
        model = get_user_model()
        fields = []


class LessonFilter(IgniteModelFilterSet):
    publishMode = Filter(source='project__publish_mode', form_field=forms.CharField(), lookups=['exact', 'in'], default_lookup='in')
    numberOfSteps = Filter(source='steps_count', form_field=forms.IntegerField(min_value=0))
    numberOfStudents = Filter(source='students_count', form_field=forms.IntegerField(min_value=0))
    idList = FilterWithOrder(source='id', form_field=forms.IntegerField(min_value=0), lookups=['in'], default_lookup='in', with_order=True)

    class Meta:
        model = Lesson
        fields = [
            'title',
            'duration',
            'application',
        ]


class ProjectFilter(IgniteModelFilterSet):
    publishMode = Filter(source='publish_mode', form_field=forms.CharField(), lookups=['exact', 'in'], default_lookup='in')
    minPublishDate = Filter(source='min_publish_date', form_field=forms.DateTimeField())
    numberOfLessons = Filter(source='lesson_count', form_field=forms.IntegerField(min_value=0))
    numberOfStudents = Filter(source='students_count', form_field=forms.IntegerField(min_value=0))
    tags = TagsFilter(source='tags')

    author = AuthorFilter(source='owner')
    idList = FilterWithOrder(source='id', form_field=forms.IntegerField(min_value=0), lookups=['in'], default_lookup='in', with_order=True)

    class Meta:
        model = Project
        fields = [
            'title',
            'description',
            'duration',
            'difficulty',
            'teacher_additional_resources',
            'license',
            'age',
        ]


class ClassroomFilter(IgniteModelFilterSet):
    numberOfProjects = Filter(source='projects_count', form_field=forms.IntegerField(min_value=0))
    numberOfStudents = Filter(source='students_approved_count', form_field=forms.IntegerField(min_value=0))
    isArchived = Filter(source='is_archived', form_field=forms.BooleanField(required=False))

    author = AuthorFilter(source='owner')
    idList = FilterWithOrder(source='id', form_field=forms.IntegerField(min_value=0), lookups=['in'], default_lookup='in', with_order=True)

    class Meta:
        model = Classroom
        fields = [
            'title',
            'description',
        ]


class ProjectStateFilter(IgniteModelFilterSet):
    stateIsCompleted = Filter(source='is_completed', form_field=forms.BooleanField(required=False))
    project = ProjectFilter(source='project')

    class Meta:
        model = ProjectState
        fields = []


class ClassroomStateClassroomFilter(IgniteModelFilterSet):
    id = Filter(source='id', form_field=forms.IntegerField(min_value=0), is_default=True)
    author = AuthorFilter(source='owner')
    isArchived = Filter(source='is_archived', form_field=forms.BooleanField(required=False))

    class Meta:
        model = Classroom
        fields = []

class ClassroomStateFilter(IgniteModelFilterSet):
    studentStatus = Filter(source='status', form_field=forms.ChoiceField(choices=ClassroomState.STATUSES, initial=ClassroomState.APPROVED_STATUS))
    # studentClassroom = Filter(source='classroom_id', form_field=forms.IntegerField(min_value=0))
    studentClassroom = ClassroomStateClassroomFilter(source='classroom')

    class Meta:
        model = ClassroomState
        fields = []


class MyUserFilter(IgniteModelFilterSet):

    class Meta:
        model = get_user_model()
        fields = [
            'name',
            'description',
        ]


class MyChildGuardianFilter(IgniteModelFilterSet):
    name = Filter(source='child__name', form_field=forms.CharField())
    description = Filter(source='child__description', form_field=forms.CharField())

    class Meta:
        model = ChildGuardian
        fields = [
            'moderator_type',
        ]


class NotificationFilter(IgniteModelFilterSet):
    actorModel = Filter(source='actor_content_type__model', form_field=forms.CharField())
    actorId = Filter(source='actor_object_id', form_field=forms.IntegerField(min_value=0))
    targetModel = Filter(source='target_content_type__model', form_field=forms.CharField())
    targetId = Filter(source='target_object_id', form_field=forms.IntegerField(min_value=0))
    subjectModel = Filter(source='subject_content_type__model', form_field=forms.CharField())
    subjectId = Filter(source='subject_object_id', form_field=forms.IntegerField(min_value=0))

    class Meta:
        model = Notification
        fields = [
            'verb',
            'level',
            'unread',
        ]


class MappedOrderingFilter(filters.OrderingFilter):
    '''
    Extends OrderingFilter with 'ordering_fields_map' attribute in view.
    Ordering is made by mapped ordering fields (higher precedence) and regular ordering fields from 'ordering_fields' attribute
    that OrderingFilter is using.
    For mapped ordering fields you must declare 'ordering_fields_map' with all the mapped fields you desire, so that the key
    is the ordering field to use in 'ordering' query string param and the value is the actual field to order in queryset.
    If value of a mapped ordering is None, then the field is mapped to the matched serializer field.

    Attributes to set in view class:
        ordering_fields_map         - dict of ordering fields map {url_ordering_field: model_field OR None}
    '''

    def get_mapped_ordering(self, ordering, view):
        ordering_fields_map = getattr(view, 'ordering_fields_map', {})

        mapped_ordering = {}
        if ordering_fields_map:
            serializer_class = getattr(view, 'serializer_class')
            serializer_fields = serializer_class().fields

            def _get_serializer_field_helper(f, f_sign=''):
                ''' Returns the serializer field source or field name if exists. '''
                serializer_f = serializer_fields.get(f, None)
                if serializer_f:
                    #for queryset.order_by() use double-underscore instead of period (like in field.source attribute):
                    return f_sign + (serializer_f.source.replace('.', '__') if serializer_f.source else f)
                return None

            signed_ordering = [('-' if field.startswith('-') else '', field.lstrip('-')) for field in ordering]
            mapped_ordering = {
                field_sign + field: ((field_sign+ordering_fields_map[field] if ordering_fields_map[field] else None) or _get_serializer_field_helper(field, field_sign)) if ordering_fields_map.has_key(field) else None
                for field_sign, field in signed_ordering
            }
            mapped_ordering = {field: mapped_field for field, mapped_field in mapped_ordering.items() if mapped_field is not None}  #remove None values (invalid mapped fields

        return mapped_ordering

    def remove_invalid_fields(self, queryset, ordering, view):
        ''' Returns ordering from ordering_fields_map (higher precedence) or default ordering_fields, and removes invalid ordering fields. '''
        valid_ordering = super(MappedOrderingFilter, self).remove_invalid_fields(queryset, ordering, view)
        mapped_ordering = self.get_mapped_ordering(ordering, view)

        #try get fields first from mapped, then from valid, and None if not valid field:
        ret_ordering = [
            mapped_ordering.get(field, field if field in valid_ordering else None)
            for field in ordering
        ]
        ret_ordering = [field for field in ret_ordering if field is not None]  #remove None values (invalid fields)
        return ret_ordering

    def get_default_ordering(self, view):
        ''' Returns default ordering mapped. '''
        #get default ordering:
        ordering = super(MappedOrderingFilter, self).get_default_ordering(view)
        if not ordering:
            return ordering

        #try get fields first from mapped, then use the field as is (do not remove invalid fields):
        mapped_ordering = self.get_mapped_ordering(ordering, view)
        ret_ordering = [
            mapped_ordering.get(field, field)
            for field in ordering
        ]
        return ret_ordering
