from rest_framework import serializers


class DynamicFieldsModelSerializer(serializers.ModelSerializer):
    """
    A ModelSerializer that takes an additional `fields` argument that
    controls which fields should be displayed.
    """

    def __init__(self, *args, **kwargs):
        super(DynamicFieldsModelSerializer, self).__init__(*args, **kwargs)

        #get dropfields and allowed:
        dropfields = getattr(self.Meta, 'dropfields', [])
        context = kwargs.get('context', {})
        allowed = context.get('allowed', [])

        #drop all fields that are specified in the `dropfields` argument and not allowed:
        actual_dropfields = set(dropfields) - set(allowed)
        if actual_dropfields:
            for field_name in actual_dropfields:
                if field_name in self.fields:
                    self.fields.pop(field_name)
