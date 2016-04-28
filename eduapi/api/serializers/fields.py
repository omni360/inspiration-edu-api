import json
from collections import OrderedDict

from jsonfield import JSONField as model_JSONField

from django.core import exceptions
from django.db.models import ForeignKey

from rest_framework.reverse import reverse
from rest_framework.settings import api_settings
from rest_framework import serializers
from rest_framework import exceptions as drf_exceptions

from utils_app import sanitize

from ..models import (
    Lesson,
    Project,
    LessonState,
    StepState,
)

from ..models import TagsField as TagsModelField


class TagsField(serializers.CharField):
    '''A TagsField that used in DRF to represent the models' TagsField AKA TagsModelField.

    We need this field because DRF doesn't catch the models' field's 
    ValidationError in to_python by itself.'''

    def __init__(self, *args, **kwargs):
        self.model_field = kwargs.pop('model_field', TagsModelField())
        super(TagsField, self).__init__(**kwargs)

    def to_internal_value(self, data):
        '''Delegate the work to the models' field'''
        value = super(TagsField, self).to_internal_value(data)

        #convert value to tags field value:
        value = self.model_field.to_python(value)

        #validate tags of the value by the tags model field:
        try:
            self.model_field.validate_tags(value)
        except exceptions.ValidationError:
            raise serializers.ValidationError('The tags cannot contain special characters and must be separated by commas.')

        return value


class URLField(serializers.URLField):
    '''
    A URLField that cleans the URL of spaces.
    '''

    def to_internal_value(self, value):

        if hasattr(value, 'replace'):
            return value.replace(' ', '+')

        return value


class JSONField(serializers.DictField):
    '''
    A helper class for DRF.

    Helps serialize JSON fields.
    '''

    def to_representation(self, obj):
        if isinstance(obj, dict) or isinstance(obj, list):
            return obj
        try:
            return json.loads(obj)
        except (ValueError):
            return obj
    
    def to_internal_value(self, value):
        if type(value) == type({}):  #allow object (JSON)
            return value
        if value is None:  #NULL turns to empty object
            return {}
        #any other value is attempted to be evaluated as a string of JSON:
        try:
            return json.loads(value)
        except (ValueError):
            raise serializers.ValidationError('Value is not a valid JSON object.')


class LookupHyperLinkedIdentityField(serializers.HyperlinkedIdentityField):
    '''
    Just like a HyperlinkedIdentityField, but accepts an object_field argument
    as well as a lookup_field argument.

    The lookup_field is the name of the field in urls.py while object_field is 
    the name of the field on the object.
    '''

    object_field = 'pk'

    def __init__(self, *args, **kwargs):

        object_field = kwargs.pop('object_field', None)
        self.object_field = object_field or self.object_field

        super(LookupHyperLinkedIdentityField, self).__init__(*args, **kwargs)

    def get_url(self, obj, view_name, request, format):
        '''
        '''
        
        object_field = getattr(obj, self.object_field, None)
        kwargs = {
            self.lookup_field: object_field
        }

        return reverse(view_name, kwargs=kwargs, request=request, format=format)


class UserStateIdentityField(serializers.HyperlinkedIdentityField):
    '''
    Returns the URL to the state in the form: /user/:id/state/<projects/lessons>/:id/
    '''

    def __init__(self, pk_url_kwarg, *args, **kwargs):
        super(UserStateIdentityField, self).__init__(*args, **kwargs)
        self.pk_url_kwarg = pk_url_kwarg

    def get_url(self, obj, view_name, request, format):

        kwargs = {}

        if isinstance(obj, LessonState):
            kwargs['user_pk'] = obj.project_state.user_id
            kwargs['project_pk'] = obj.project_state.project_id
        else:
            kwargs['user_pk'] = obj.user_id
        kwargs[self.pk_url_kwarg] = getattr(obj, self.lookup_field, None)

        return reverse(view_name, kwargs=kwargs, request=request, format=format)


class InlineListRelatedField(serializers.Field):
    '''
    This field is used to translate a FK related model to an inline list
    of values.

    The field expects the following special kwargs:
    - model - The class of the model being linked.
    - slug_field - The name of the field that should appear in the inline list.
    - order - Optional, the order by which the list should be constructed.
    '''

    def __init__(self, *args, **kwargs):

        self.slug_field = kwargs.pop('slug_field')
        self.model = kwargs.pop('model')
        self.order = kwargs.pop('order', '')
        self.slug_validators = kwargs.pop('slug_validators', [])
        self.slug_full_clean = kwargs.pop('slug_full_clean', not self.slug_validators)  #default: use slug full_clean if slug_validators are empty

        super(InlineListRelatedField, self).__init__(*args, **kwargs)

        # Need to be done after super.__init__
        # Stores whether the slug field is a JSON field or not.
        self.is_jsonfield = isinstance(
            self.model._meta.get_field(self.slug_field), 
            model_JSONField
        )

    def to_representation(self, obj):

        # Get the values from the object.
        # Note: Doing this with Python and not QuerySet because otherwise
        # prefetch_related() optimizations are discarded.
        values = obj.all()
        values = sorted(values, key=lambda z: getattr(z, self.order or 'id'))
        values = [unicode(getattr(v, self.slug_field)) for v in values]

        # Convert to a list of JSONs or to a regular list according to the 
        # field type.
        if self.is_jsonfield:
            return [json.loads(x) for x in values]
        else:
            return list(values)

    def to_internal_value(self, value):
        '''
        '''

        if type(value) != type([]):
            return value

        new_objs = value

        # Create new objects.
        if self.order:
            new_objs = [
                self.model(**{self.slug_field: val, self.order: idx})
                for idx, val
                in enumerate(new_objs)
                if val
            ]
        else:
            new_objs = [
                self.model(**{self.slug_field: val})
                for idx, val
                in enumerate(new_objs)
                if val
            ]

        return new_objs

    def run_validators(self, value):
        super(InlineListRelatedField, self).run_validators(value)

        # Run slug validators for each item in the list:
        if isinstance(value, list):
            errors = []

            for slug_obj in value:
                slug_value = getattr(slug_obj, self.slug_field)
                if self.slug_validators:
                    for slug_validator in self.slug_validators:
                        try:
                            slug_validator(slug_value)
                        except exceptions.ValidationError as e:
                            if hasattr(e, 'code') and e.code in self.error_messages:
                                message = self.error_messages[e.code]
                                if e.params:
                                    message = message % e.params
                                errors.append(message)
                            else:
                                errors.extend(e.messages)
                if self.slug_full_clean:
                    try:
                        model_fk = filter(lambda x: isinstance(x, ForeignKey) and x.rel.to is self.parent.Meta.model, self.model._meta.fields)[0]
                        slug_obj.full_clean(exclude=[model_fk.name])
                    except exceptions.ValidationError as e:
                        if hasattr(e, 'code') and e.code in self.error_messages:
                            message = self.error_messages[e.code]
                            if e.params:
                                message = message % e.params
                            errors.append(message)
                        else:
                            errors.extend(e.messages)

            if errors:
                raise exceptions.ValidationError(errors)


class StepHyperlinkedField(serializers.HyperlinkedRelatedField):
    '''
    A hyperlinked field specific for Step.

    We need this because the URL of Step is non-trivial.
    '''

    def get_url(self, obj, view_name, request, format):
        kwargs = {'project_pk': obj.lesson.project_id, 'lesson_pk': obj.lesson_id, 'order': obj.order}
        return reverse(view_name, kwargs=kwargs, request=request, format=format)

    def get_object(self, view_name, view_args, view_kwargs):
        lesson_id = view_kwargs['lesson_id']
        order = view_kwargs['order']
        return self.get_queryset().get(lesson_id=lesson_id, order=order)


class ReviewHyperlinkedIdentityField(serializers.HyperlinkedIdentityField):
    '''
    A hyperlink field to a Review.

    The special thing about reviews, is that they form a generic relationship
    with other objects and their API is nested in other objects' APIs.

    E.g. - /projects/:id/reviews/
    '''

    def __init__(self, *args, **kwargs):

        # view_name is required by HyperlinkedIdentityField, but we don't need
        # it because we calculate it ourselves.
        kwargs['view_name'] = ''
        super(ReviewHyperlinkedIdentityField, self).__init__(*args, **kwargs)

    def get_url(self, obj, view_name, request, format):
        '''
        Returns a URL based on the content_object of Review.
        '''
        kwargs = {}
        if not obj:
            return None
        if type(obj.content_object).__name__ == 'Project':
            view_name = 'api:project-review-detail'
            pk_name = 'project_pk'
        kwargs.update({
            pk_name: obj.content_object.id,
            'pk': obj.id,
        })
        return reverse(view_name, kwargs=kwargs, request=request, format=format)

    def get_object(self, view_name, view_args, view_kwargs):
        '''
        Returns a Review based on the URL.

        Note that we want to make sure that
        only the review is returned only if it's PK is in the context of the 
        nesting object. That is, if the user makes a(n illegal) call to 
        /projects/1/reviews/4/ and the Review with the PK 4 is actually connected
        to project 2, we would like to return a 404 instead of the review.
        '''

        if 'project_pk' in view_kwargs:
            return Project.objects.filter(id=view_kwargs['project_pk']).reviews.get(id=view_kwargs['pk'])

class ReviewedItemHyperlinkedIdentityField(serializers.HyperlinkedIdentityField):
    '''
    A hyperlink field to a Reviewed item.

    The special thing about reviews, is that they form a generic relationship
    with other objects and their API is nested in other objects' APIs.

    E.g. - /projects/:id/reviews/
    '''

    def __init__(self, *args, **kwargs):

        # view_name is required by HyperlinkedIdentityField, but we don't need
        # it because we calculate it ourselves.
        kwargs['view_name'] = ''
        super(ReviewedItemHyperlinkedIdentityField, self).__init__(*args, **kwargs)

    def get_url(self, obj, view_name, request, format):
        '''
        Returns a URL based on the content_object of Review.
        '''

        kwargs = {}
        if type(obj.content_object).__name__ == 'Project':
            view_name = 'api:project-detail'

        kwargs.update({
            'pk': obj.content_object.id
        })
        return reverse(view_name, kwargs=kwargs, request=request, format=format)


class StepHyperlinkedIdentityField(serializers.HyperlinkedIdentityField):
    '''
    A hyperlinked identity field specific for Step, supporting also draft URL.

    We need this because the URL of Step is non-trivial.
    '''
    def __init__(self, *args, **kwargs):
        self.draft_view_name = kwargs.pop('draft_view_name', None)
        super(StepHyperlinkedIdentityField, self).__init__(*args, **kwargs)

    def get_url(self, obj, view_name, request, format):
        # If obj is draft, then use draft_view_name:
        if obj.is_draft and self.draft_view_name:
            kwargs = {'project_pk': obj.lesson.project.draft_origin_id, 'lesson_pk': obj.lesson.draft_origin_id, 'order': obj.order}
            view_name = self.draft_view_name
        else:
            kwargs = {'project_pk': obj.lesson.project_id, 'lesson_pk': obj.lesson_id, 'order': obj.order}
        return reverse(view_name, kwargs=kwargs, request=request, format=format)

    def get_object(self, view_name, view_args, view_kwargs):
        lesson_id = view_kwargs['lesson_id']
        order = view_kwargs['order']
        return self.get_queryset().get(lesson_id=lesson_id, order=order)


class VersionedHyperlinkedIdentityField(serializers.HyperlinkedIdentityField):
    '''
    A hyperlinked field specific for Versioned objects.
    '''

    def get_url(self, obj, view_name, request, format):
        kwargs = {'base_id': obj.base_id, 'version_id': obj.id}
        return reverse(view_name, kwargs=kwargs, request=request, format=format)


class OrderedSlugRelatedField(serializers.SlugRelatedField):
    '''
    A field that converts an ObjectAInObjectB related set to an
    ordered list of objects.

    For example, is used to convert a ProjectInClassroom related set to an ordered
    list of projects.

    Expects the following initialization variables:
        * object_id_field e.g. - 'lesson_id', 'project_id'.
        * through_model e.g. - ProjectInClassroom

    NOTE: Throughout the below documentation, A refers to the ordered object
          and B refers to the containing object.
    '''

    def __init__(self, order_field='order', *args, **kwargs):
        self.order_field = order_field
        super(OrderedSlugRelatedField, self).__init__(*args, **kwargs)

    @classmethod
    def many_init(cls, *args, **kwargs):
        list_kwargs = {'child_relation': cls(*args, **kwargs)}
        for key in kwargs.keys():
            if key in serializers.MANY_RELATION_KWARGS:
                list_kwargs[key] = kwargs[key]
        return ManyOrderedSlugRelatedField(**list_kwargs)

class ManyOrderedSlugRelatedField(serializers.ManyRelatedField):
    def to_internal_value(self, data):
        value = super(ManyOrderedSlugRelatedField, self).to_internal_value(data)

        for idx, single_value in enumerate(value):
            setattr(single_value, self.child_relation.order_field, idx)

        return value

class OrderedSerializer(serializers.Serializer):
    def __init__(self, instance, data, **kwargs):


        super(OrderedSerializer, self).__init__(instance=instance, data=data, **kwargs)


class OrderedListSerializer(serializers.ListSerializer):
    def to_internal_value(self, data):
        value = super(OrderedListSerializer, self).to_internal_value(data)

        #add order

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def save(self, **kwargs):
        pass


class OrderedSerializerRelatedField(serializers.Serializer):
    '''
    Ordered serializer list objects.
    On save, it help to automatically set the 'order' field of the serializer according to the order in the list.

    Parameters to set:
        * serializer                - Serializer class of the field (subclass of Serializer).
        * order_serializer_field    - the 'order' field to set in the serializer.
        * force_order_as_list       - whether to truncate 'order' fields on the serializer objects in the list.
    Usually use this with many=True and allow_add_remove=True.
    '''
    def __new__(cls, *args, **kwargs):
        #get arguments from constructor:
        serializer = kwargs.pop('serializer', None)
        order_serializer_field = kwargs.pop('order_serializer_field', 'order')
        force_order_as_list = kwargs.pop('force_order_as_list', True)

        #assert serializer is Serializer:
        if not issubclass(serializer, serializers.Serializer):
            raise serializers.ValidationError('Expecting \'serializer\' to be subclass of Serializer.')

        #create new class of ordered serializer:
        class OrderedSerializer(serializer):

            def field_from_native(self, data, files, field_name, into):
                '''
                Automatically adds 'order' field to serialized data according to the order in the list.
                '''
                # validate field must be list:
                try:
                    value = data[field_name]
                except KeyError:
                    if self.partial:
                        return
                    value = self.get_default_value()
                if not isinstance(value, list):
                    raise serializers.ValidationError(self.error_messages['must_be_list'])

                # Add the order to each ordered serialized data in the containing object.
                for idx, a_in_b_data in enumerate(value):
                    if force_order_as_list or order_serializer_field not in a_in_b_data:
                        a_in_b_data[order_serializer_field] = idx

                # First perform the regular from_native operation.
                super(OrderedSerializer, self).field_from_native(data, files, field_name, into)

        #rename the ordered serializer:
        OrderedSerializer.__name__ = 'Ordered' + serializer.__name__

        #force init arguments for serializer:
        kwargs.update({
            'many': True,
        })

        #get the new ordered serializer instance:
        instance = OrderedSerializer(*args, **kwargs)

        #assert serializer 'order' field:
        if order_serializer_field not in instance.child.fields:
            raise serializers.ValidationError('Serializer order field \'%s\' is not defined in the serializer.' %(order_serializer_field,))

        return instance


class ViewedStepsRelatedField(serializers.RelatedField):
    '''
    A field that converts a viewed_steps related set to a list
    of viewed steps IDs.
    '''

    def to_representation(self, value):
        '''Return the ID of the step from the StepState object'''
        return value.id

    def to_internal_value(self, data):
        '''
        Use the ID of the step (from the JSON data) to return a
        StepState object.

        Note that this does not save the StepState in the DB,
        it just creates it.
        '''

        return StepState(step_id=data)

    # def get_value(self, dictionary):
    #     """
    #     Remove the old StepState values, save new ones if not already exist.
    #     """

    #     # NOTE: object might be problematic here.
        
    #     # First perform the regular get_value operation.
    #     value = super(ViewedStepsRelatedField, self).get_value(dictionary)

    #     # If the object exists and the request contains data
    #     if self.parent.object and data and data.get('viewedSteps'):
    #         all_viewed_step_states = self.parent.object.step_states.all()
    #         new_viewed_steps_ids = data.get('viewedSteps')

    #         # Delete StepStates that are no longer viewed
    #         to_delete_viewed_steps = all_viewed_step_states.exclude(step__pk__in=new_viewed_steps_ids)
    #         to_delete_viewed_steps.delete()

    #         # Create new viewed steps, if they don't already exist:
    #         to_create_steps = self.parent.object.lesson.steps.all()  #all lesson steps
    #         to_create_steps = to_create_steps.exclude(pk__in=[s.step_id for s in all_viewed_step_states])  #lesson steps not viewed
    #         to_create_steps = to_create_steps.filter(pk__in=new_viewed_steps_ids)  #lesson steps not viewed to create
    #         for step in to_create_steps:
    #             StepState(step=step, lesson_state=self.parent.object).save()


class HtmlField(serializers.CharField):
    '''
    A field that accepts HTML string, and ensures it is safe HTML (sanitize).
    '''

    # Defaults sanitize options used by sanitize_html() method.
    defaults_sanitize_options = sanitize.DEFAULTS_CLEAN

    def __init__(self, *args, **kwargs):
        self._sanitize_options = kwargs.pop('sanitize_options', self.defaults_sanitize_options)
        super(HtmlField, self).__init__(*args, **kwargs)

    def to_internal_value(self, data):
        '''
        Sanitize the HTML string.
        '''

        #sanitize the HTML string:
        return sanitize.sanitize_html(data, options=self._sanitize_options)


class LessonHyperlinkedIdentityField(serializers.HyperlinkedIdentityField):
    '''
    Receives a Lesson object ad returns an identity hyperlink to the lesson
    details API endpoint (lesson under project).
    '''
    def __init__(self, *args, **kwargs):
        self.draft_view_name = kwargs.pop('draft_view_name', None)
        super(LessonHyperlinkedIdentityField, self).__init__(*args, **kwargs)

    def get_url(self, obj, view_name, request, format):
        # If obj is draft, then use draft_view_name:
        if obj.is_draft and self.draft_view_name:
            kwargs = {'project_pk': obj.project.draft_origin_id, 'lesson_pk': obj.draft_origin_id}
            view_name = self.draft_view_name
        else:
            kwargs = {'project_pk': obj.project_id, 'pk': obj.id}
        return reverse(view_name, kwargs=kwargs, request=request, format=format)

class LessonHyperlinkedField(serializers.HyperlinkedRelatedField):
    '''
    Receives a Lesson object and returns a hyperlink to the lesson
    details API endpoint (lesson under project).
    '''
    def __init__(self, *args, **kwargs):
        self.draft_view_name = kwargs.pop('draft_view_name', None)
        super(LessonHyperlinkedField, self).__init__(*args, **kwargs)

    def use_pk_only_optimization(self):
        return False

    def get_url(self, obj, view_name, request, format):
        # If obj is draft, then use draft_view_name:
        if obj.is_draft and self.draft_view_name:
            kwargs = {'project_pk': obj.project.draft_origin_id, 'lesson_pk': obj.draft_origin_id}
            view_name = self.draft_view_name
        else:
            kwargs = {'project_pk': obj.project_id, 'pk': obj.id}
        return reverse(view_name, kwargs=kwargs, request=request, format=format)

class LessonStateHyperlinkedField(serializers.HyperlinkedRelatedField):
    '''
    Receives a LessonState object and returns a hyperlink to the lesson state
    API endpoint (lesson state under project state).
    '''

    def get_url(self, obj, view_name, request, format):
        kwargs = {'user_pk': obj.project_state.user_id, 'project_pk': obj.project_state.project_id, 'lesson_pk': obj.lesson_id}
        return reverse(view_name, kwargs=kwargs, request=request, format=format)

class ProjectHyperlinkedIdentityField(serializers.HyperlinkedIdentityField):
    '''
    Receives a Project object and returns an identity hyperlink to the project
    details API endpoint.
    '''
    def __init__(self, *args, **kwargs):
        self.draft_view_name = kwargs.pop('draft_view_name', None)
        super(ProjectHyperlinkedIdentityField, self).__init__(*args, **kwargs)

    def get_url(self, obj, view_name, request, format):
        # If obj is draft, then use draft_view_name:
        if obj.is_draft and self.draft_view_name:
            kwargs = {'project_pk': obj.draft_origin_id}
            view_name = self.draft_view_name
        else:
            kwargs = {'pk': obj.id}
        return reverse(view_name, kwargs=kwargs, request=request, format=format)

class ProjectInObjectHyperlinkedField(serializers.HyperlinkedRelatedField):
    '''
    Receives a ProjectInClassroom object and returns an hyperlink to the project
    details API endpoint.
    '''

    def get_url(self, obj, view_name, request, format):
        kwargs = {'pk': obj.project_id}
        return reverse(view_name, kwargs=kwargs, request=request, format=format)


class VersionRelatedField(serializers.RelatedField):
    """
    A related field for a versioned objects,
    returns (base_id, version_id) tuple as a string.
    """
    def to_representation(self, value):
        return "(%s, %s)" % (value.base_id, value.id)
