from django.db import models
from django.conf import settings

from utils_app.models import TimestampedModel


class OwnerDelegate(TimestampedModel):
    """
    This model represents delegated users for an owner user.
    """

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='ownerdelegate_delegate_set')

    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='ownerdelegate_delegator_set')

    class Meta:
        unique_together = (('owner', 'user'),)
