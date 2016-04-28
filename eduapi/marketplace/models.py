from django.db import models
from django.conf import settings

from utils_app.models import TimestampedModel

class Purchase(TimestampedModel):
    """A purchase of a project by a user"""

    TEACH_PERM = 'teacher'
    VIEW_PERM = 'viewer'
    PERMISSION_TYPES = (
        (TEACH_PERM, 'teach'),  # Project.PERMS['TEACH']
        (VIEW_PERM, 'view'),  # Project.PERMS['VIEW']
    )

    project = models.ForeignKey('api.Project', related_name='purchases')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='purchases')
    permission = models.CharField(choices=PERMISSION_TYPES, max_length=50, help_text='The permission that the purchase grants.')

    class Meta:
        unique_together = (('project', 'user'),)
