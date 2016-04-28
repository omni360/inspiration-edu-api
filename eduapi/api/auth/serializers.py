from django.contrib.auth import authenticate, get_user_model
from django.utils.translation import ugettext_lazy as _

from rest_framework import serializers


class AuthTokenSerializer(serializers.Serializer):
    '''
    Just like DRF's AuthTokenSerializer, but uses session_id and 
    secure_session_id as the credentials instead of username and password.
    '''

    sessionId = serializers.CharField()
    secureSessionId = serializers.CharField()

    def validate(self, attrs):
        session_id = attrs.get('sessionId')
        secure_session_id = attrs.get('secureSessionId')

        if session_id and secure_session_id:
            user = authenticate(
                session_id=session_id,
                secure_session_id=secure_session_id,
            )

            if user:
                if not user.is_active:
                    msg = _('User account is disabled.')
                    raise serializers.ValidationError(msg)
                attrs['user'] = user
                return attrs
            else:
                msg = _('Unable to login with provided credentials.')
                raise serializers.ValidationError(msg)
        else:
            msg = _('Must include "sessionId" and "secureSessionId"')
            raise serializers.ValidationError(msg)


class PasswordResetSerializer(serializers.Serializer):
    '''
    Serialize password reset
    '''
    sessionId       = serializers.CharField()
    secureSessionId = serializers.CharField()
    password        = serializers.RegexField(regex='\S+', max_length=50, min_length=8)
