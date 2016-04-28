from django.utils import dateparse

from django.core import validators
from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible


@deconstructible
class InlineVideoJSONValidator(object):
    '''
    Validates inline JSON for video field.
    '''
    error_messages = {
        'invalid': 'Enter a valid value: { vendor, id, startTime?, endTime?, meta?: { published?, author?, title?, duration? } }',
        'vendor_not_allowed': 'Vendor \'%s\' is not allowed.',
        'invalid_vendor_id': 'Video ID is invalid.',
        'invalid_meta_field': 'Meta \'%s\' field is invalid.',
        'invalid_time': '\'%s\' field is invalid time.',
        'invalid_time_delta': '\'endTime\' must be greater than \'startTime\'.',
    }
    allowed_vendors = None
    vendor_id_validators = []

    def __init__(self, allowed_vendors=None, vendor_id_validators=None):
        if allowed_vendors:
            self.allowed_vendors = allowed_vendors
        if vendor_id_validators:
            self.vendor_id_validators = vendor_id_validators

    def _duration_to_str(self, duration_timedelta):
        if not duration_timedelta.days:
            duration_str = str(duration_timedelta)
        else:
            no_days_duration = dateparse.datetime.timedelta(seconds=duration_timedelta.seconds)
            no_days_duration_str = str(no_days_duration)
            hours, minutes_seconds = no_days_duration_str.split(':', 1)
            duration_str = str(int(hours) + duration_timedelta.days*24) + ':' + minutes_seconds
        return duration_str

    def __call__(self, value):
        if not isinstance(value, dict):
            self._raise_error('invalid')

        #check for valid keys:
        if len(set(value.keys()) - {'vendor', 'id', 'startTime', 'endTime', 'meta',}):
            self._raise_error('invalid')

        #check vendor is allowed:
        video_vendor = value.get('vendor', '')
        if self.allowed_vendors is not None:
            if video_vendor not in self.allowed_vendors:
                self._raise_error('vendor_not_allowed', (video_vendor,))

        #check vendor id:
        vendor_id_validator = self.vendor_id_validators.get(video_vendor)
        video_id = value.get('id', '')
        if vendor_id_validator:
            if not vendor_id_validator(video_id):
                self._raise_error('invalid_vendor_id')

        #check startTime:
        video_start_time = value.get('startTime')
        video_start_timedelta = None
        if video_start_time:
            #validate and clean time string:
            video_start_timedelta = dateparse.parse_duration(video_start_time)
            if video_start_timedelta is None:
                self._raise_error('invalid_time', ('startTime',))
            video_start_time = self._duration_to_str(video_start_timedelta)
            value['startTime'] = video_start_time

        #check endTime:
        video_end_time = value.get('endTime')
        if video_end_time:
            #validate and clean time string:
            video_end_timedelta = dateparse.parse_duration(video_end_time)
            if video_end_timedelta is None:
                self._raise_error('invalid_time', ('endTime',))
            video_end_time = self._duration_to_str(video_end_timedelta)
            value['endTime'] = video_end_time

            #validate timedelta between end and start times:
            if video_start_timedelta and video_end_timedelta:
                if video_end_timedelta <= video_start_timedelta:
                    self._raise_error('invalid_time_delta')

        #check meta, in case exists:
        if 'meta' in value:
            if len(set(value['meta'].keys()) - {'published', 'author', 'title', 'duration',}):
                self._raise_error('invalid')
            if 'published' in value['meta'] and not dateparse.parse_datetime(value['meta']['published']):
                self._raise_error('invalid_meta_field', ('published',))
            for f in ['author', 'title']:
                if f in value['meta'] and (not isinstance(value['meta'][f], basestring) or len(value['meta'][f]) > 255):
                    self._raise_error('invalid_meta_field', (f,))
            if 'duration' in value['meta']:
                video_duration_timedelta = dateparse.parse_duration(value['meta']['duration'])
                if video_duration_timedelta is None:
                    self._raise_error('invalid_meta_field', ('duration',))
                value['meta']['duration'] = self._duration_to_str(video_duration_timedelta)

    def _raise_error(self, error_code, msg_args=tuple()):
        raise ValidationError(self.error_messages[error_code] % msg_args, code=error_code)


@deconstructible
class InlineTeacherFileJSONValidator(object):
    '''
    Validates inline JSON for teacher file field.
    '''
    error_messages = {
        'invalid': 'Enter a valid value: { url, size, name, time }',
        'invalid_field': 'Field \'%s\' is invalid.',
    }

    def __call__(self, value):
        if not isinstance(value, dict):
            self._raise_error('invalid')

        #check all keys exist:
        if set(value.keys()) != {'url', 'size', 'name', 'time',}:
            self._raise_error('invalid')

        #check url:
        try:
            validators.URLValidator()(value['url'])
        except Exception:
            self._raise_error('invalid_field', ('url',))
        if len(value['url']) > 500:
            self._raise_error('invalid_field', ('url',))

        #check size:
        if type(value['size']) is not int or value['size'] < 0:
            self._raise_error('invalid_field', ('size',))

        #check name:
        if not isinstance(value['name'], basestring) or not value['name'] or len(value['name']) > 255:
            self._raise_error('invalid_field', ('name',))

        #check time:
        if not dateparse.parse_datetime(value['time']):
            self._raise_error('invalid_field', ('time',))

    def _raise_error(self, error_code, msg_args=tuple()):
        raise ValidationError(self.error_messages[error_code] % msg_args, code=error_code)


@deconstructible
class InstructablesJSONValidator(object):
    '''
    Validates JSON for instructables field.
    '''
    error_messages = {
        'invalid': 'Enter a valid value: { urlId }',
        'invalid_field': 'Field \'%s\' is invalid.',
    }

    def __call__(self, value):
        if not isinstance(value, dict):
            self._raise_error('invalid')

        #check all keys exist:
        if set(value.keys()) != {'urlId',}:
            self._raise_error('invalid')

        #check urlId (validate as url slug):
        try:
            validators.validate_slug(value['urlId'])
        except ValidationError:
            self._raise_error('invalid_field', ('urlId',))

    def _raise_error(self, error_code, msg_args=tuple()):
        raise ValidationError(self.error_messages[error_code] % msg_args, code=error_code)


@deconstructible
class InstructionJSONValidator(object):
    '''
    Validates inline JSON for video field.
    '''
    error_messages = {
        'invalid': 'Enter a valid values: { description, image, hint, id, order }',
        'invalid_field': 'Field \'%s\' is invalid.',
    }

    def __call__(self, value):
        if not isinstance(value, dict):
            self._raise_error('invalid')

        #check description keys exist:
        if not 'description' in set(value.keys()) or not value.get('description'):
            self._raise_error('invalid')

        #check all keys exist:
        if len(set(value.keys()) - { 'description', 'image', 'hint', 'id', 'order' }) > 0:
            self._raise_error('invalid')

        #check image:
        if value.get('image'):
            try:
                validators.URLValidator()(value['image'])
            except ValidationError:
                self._raise_error('invalid_field', ('image',))
            if len(value['image']) > 500:
                self._raise_error('invalid_field', ('image',))


    def _raise_error(self, error_code, msg_args=tuple()):
        raise ValidationError(self.error_messages[error_code] % msg_args, code=error_code)


@deconstructible
class SeparatorJSONValidator(object):
    '''
    Validates JSON for separator field.
    '''
    error_messages = {
        'invalid': 'Enter a valid value: { before, label }',
        'invalid_field': 'Field \'%s\' is invalid.',
    }

    def __call__(self, value):
        if not isinstance(value, dict):
            self._raise_error('invalid')

        #check all keys exist:
        if set(value.keys()) != {'before', 'label',}:
            self._raise_error('invalid')

        #check before:
        if type(value['before']) is not int or value['before'] < 0:
            self._raise_error('invalid_field', ('before',))

        #check label:
        if not isinstance(value['label'], basestring) or not value['label'] or len(value['label']) > 140:
            self._raise_error('invalid_field', ('label',))

    def _raise_error(self, error_code, msg_args=tuple()):
        raise ValidationError(self.error_messages[error_code] % msg_args, code=error_code)
