from django.db.models import fields, SubfieldBase
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError

from jsonfield import JSONField
from jsonfield.subclassing import SubfieldBase as JSONSubfieldBase
from jsonfield.fields import JSONFormFieldBase, JSONFieldBase, JSONFormField

import re


class TagsField(fields.CharField):
    """
    Tags field is list tags separated by commas.
    A tag is consisting of letters, spaces, numbers, underscores or hyphens.
    NOTE: On save, the field tags are trimmed.
    """
    # This metaclass makes the field to be constructed via .to_python() method whenever set field attribute:
    __metaclass__ = SubfieldBase

    tag_regex = r'^(?!\s)[\w\s\-]+(?<!\s)$'
    tag_separator = ',' #cannot be a white space

    def get_tags_list(self, value):
        """
        Returns list of tags strings, with omitting empty tags.
        """
        return [x for x in re.split(r'\s*' + re.escape(self.tag_separator.strip()) + '\s*', value.strip()) if x]

    def validate_tags(self, value):
        single_tag_regex = re.compile(self.tag_regex)
        for single_tag_string in self.get_tags_list(value):
            if not single_tag_regex.match(single_tag_string):
                raise ValidationError('Enter slugs (consisting of letters, spaces, numbers, underscores or hyphens) separated by comma', code='invalid_tags')

    def validate(self, value, model_instance):
        super(TagsField, self).validate(value, model_instance)
        self.validate_tags(value)

    def get_prep_value(self, value):
        """
        Get value to save in DB. Here, validate tags.
        """
        value = super(TagsField, self).get_prep_value(value)
        self.validate_tags(value)
        return value

    def to_python(self, value):
        value = super(TagsField, self).to_python(value)
        return self.tag_separator.join(self.get_tags_list(value))


class ArrayJSONField(ArrayField):
    """
    This field handles array of JSONField's.
    When JSONField is set on object loading from database, it decodes json string. ArrayField does not init the
    json strings, so this class does that work.

    TODO: When available (probably Django 1.9) - Remove this field class and use Django ArrayField with JSON (DictField?).
    """
    # This metaclass makes the field to be constructed via .pre_init() method whenever set field attribute:
    # Note: .pre_init() decodes json string only when object is loaded from database, otherwise what you set is what you get.
    __metaclass__ = JSONSubfieldBase

    def pre_init(self, value, obj):
        if hasattr(value, '__iter__'):
            value = [self.base_field.pre_init(val, obj) for val in value]
        return value

    # This declares to use JSONFormField for the form field. We use the same as regular JSON form field.
    # Note: Some of the behavior is copied (and modified) from jsonfield.JSONFieldBase.
    form_class = JSONFormField
    load_kwargs = {}

    def formfield(self, **kwargs):
        if "form_class" not in kwargs:
            kwargs["form_class"] = self.form_class

        field = super(ArrayField, self).formfield(**kwargs)

        if isinstance(field, JSONFormFieldBase):
            field.load_kwargs = self.load_kwargs

        if not field.help_text:
            field.help_text = "Enter valid JSON"

        return field

    def value_from_object(self, obj):
        value = super(ArrayJSONField, self).value_from_object(obj)
        if self.null and value is None:
            return None
        # since base_field is JSONField, we can use it for dumping the value for display:
        return self.base_field.dumps_for_display(value)
