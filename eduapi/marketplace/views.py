from django.conf import settings

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from .models import Purchase

from api.models import Project
from api.tasks import send_mail_template

class MarketplaceCallbacks(APIView):
    """Callbacks for Marketplace"""

    # TODO: Use serializer_class = MkpPurchaseNotificationSerializer attribute instead of _get_serializer_class() method.
    #       That was used as hack to pass tests.

    def _get_serializer_class(self):
        # This is used to let tests set the serializer_class to use:
        if hasattr(self, 'serializer_class'):
            return self.serializer_class
        # Return default serializer class:
        from .serializers import MkpPurchaseNotificationSerializer
        return MkpPurchaseNotificationSerializer

    def post(self, request):
        """An API endpoint for Marketplace to notify us when an Arduino kit is purchased"""

        serializer_class = self._get_serializer_class()

        # Project IDs that should be unlocked for the Arduino content
        projects_ids_to_unlock = {
            arduino_purchase_id : settings.ARDUINO_PROJECTS_IDS
            for arduino_purchase_id in settings.ARDUINO_PURCHASE_IDS
        }

        # Validate using serializer.
        serializer = serializer_class(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Get the user from the serializer.
        user = serializer.validated_data['user']

        purchased_item_id = serializer.validated_data['purchasedItemId']

        # Register the purchases in the database.
        for p_id in projects_ids_to_unlock[purchased_item_id]:

            # Update or create the purchases.
            Purchase.objects.update_or_create(
                user=user,
                project_id=p_id,
                defaults={'permission': Purchase.TEACH_PERM},
            )

        # Send an email to the user letting her know of the purchase.
        send_mail_template.delay(
            settings.EMAIL_TEMPLATES_NAMES['ARDUINO_PURCHASE_NOTIFICATION'], 
            [{'recipient': {'name': user.name, 'address': user.email}}],
        )

        return Response(status=status.HTTP_200_OK)
