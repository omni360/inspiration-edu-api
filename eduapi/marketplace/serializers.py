from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.exceptions import PermissionDenied

from rest_framework import serializers

from api.auth.serializers import AuthTokenSerializer

class MkpPurchaseNotificationSerializer(AuthTokenSerializer):
    """Validates and serializes data that is sent to the Marketplace callbacks API"""

    purchasedItemId = serializers.ChoiceField(choices=settings.ARDUINO_PURCHASE_IDS)
    mkpSecretToken = serializers.CharField(required=False)

    def validate(self, attrs):

        # Check that the secret token is correct.
        mkp_secret_token = attrs.get('mkpSecretToken', None)
        if mkp_secret_token != settings.MKP_SECRET_TOKEN:
            raise PermissionDenied()
            
        # Delegate user creation/retrieval to AuthTokenSerializer
        attrs = super(MkpPurchaseNotificationSerializer, self).validate(attrs)
        purchased_item_id = attrs.get('purchasedItemId')

        return attrs
