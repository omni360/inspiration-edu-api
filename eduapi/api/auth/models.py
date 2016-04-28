from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.contrib.auth.models import UserManager 
from django.utils.translation import ugettext_lazy as _
from django.conf import settings
from django.dispatch import receiver
from django.db.models.signals import post_save
from django_counter_field import CounterField

from rest_framework.authtoken.models import Token

from utils_app.models import TimestampedModel, DeleteStatusModel

class IgniteUser(AbstractBaseUser, PermissionsMixin, TimestampedModel):
    '''
    The Ignite user.
    '''

    # Under this age (excluding), a user is a child according to COPPA
    COPPA_CHILD_THRESHOLD = 13

    TEACHER = 'teacher'
    STUDENT = 'student'
    PARENT = 'parent'
    OTHER = 'other'
    UNDECIDED = 'undecided'
    USER_TYPES = (
        (TEACHER, 'Teacher'),
        (STUDENT, 'Student'),
        (PARENT, 'Parent'),
        (OTHER, 'Other'),
        (UNDECIDED, 'Undecided'),
    )

    email = models.EmailField(_('email address'), blank=True)
    is_staff = models.BooleanField(_('staff status'), default=False,
        help_text=_('Designates whether the user can log into this admin '
                    'site.'))
    is_active = models.BooleanField(_('active'), default=True,
        help_text=_('Designates whether this user should be treated as '
                    'active. Unselect this instead of deleting accounts.'))
    member_id = models.CharField(help_text='The Spark Drive API Member ID', max_length=50, unique=True)
    oxygen_id = models.CharField(help_text='The Oxygen Member ID', max_length=50, unique=True)
    name = models.CharField(help_text='The user\'s name', max_length=140, blank=True, null=True)
    short_name = models.CharField(help_text='The user\'s short name. Could be given name or any other name in MEMBERINITIALNAME', max_length=140, blank=True, null=True)
    avatar = models.CharField(help_text='The URL of the user\'s avatar', max_length=512, null=True, blank=True)
    description = models.CharField(help_text='The description of the user', max_length=500, blank=True, default='')

    user_type = models.CharField(help_text='The user type', choices=USER_TYPES, max_length=10, default=UNDECIDED)

    show_authoring_tooltips = models.BooleanField(help_text='Flag whether to show user authoring tooltips in ProjectIgnite', default=True)

    # COPPA Stuff
    is_child = models.BooleanField(default=False, help_text='Is the user under COPPA_CHILD_THRESHOLD years old')
    is_verified_adult = models.BooleanField(default=False, help_text='Was the user verified as an adult')
    is_approved = models.BooleanField(default=False, help_text='Does the user have a moderator')
    parent_email = models.EmailField(help_text='The parent email child entered during registration', null=True, blank=True)
    guardians = models.ManyToManyField('self', through='ChildGuardian', through_fields=('child', 'guardian'), related_name='children', symmetrical=False, blank=True)

    # Delegate Stuff
    delegates = models.ManyToManyField('self', through='OwnerDelegate', through_fields=('owner', 'user'), related_name='delegators', symmetrical=False, blank=True)

    objects = UserManager()

    # Counters
    editors_count  = CounterField()

    USERNAME_FIELD = 'member_id'
    # REQUIRED_FIELDS = ['oxygen_id']

    def username(self):
        return self.name

    def get_full_name(self):
        return self.name

    def get_short_name(self):
        return self.short_name

    def __unicode__(self):
        return self.get_full_name() or 'no name'

    def get_cache_childguardian_guardian(self, guardian):
        """Returns the ChildGuardian object of the user's guardian."""
        # Get the guardian's ChildGuardian object for self child user, either from a cached prefetch on child/guardian
        # or by filtering childguardian set.
        # Note: (guardian, child) is unique in ChildGuardian, therefore child_guardians will return at most 1 result.
        child = self
        child_guardians = getattr(
            child,
            'user_%s_guardian' % guardian.id,
            getattr(
                guardian,
                'user_%s_child' % child.id,
                child.childguardian_guardian_set.filter(guardian=guardian)
            )
        )
        child_guardians = list(child_guardians[:1])  # materialize and prefetch child guardian (first only)
        setattr(child, 'user_%s_guardian' % guardian.id, child_guardians)  # cache prefetch in child
        setattr(guardian, 'user_%s_child' % child.id, child_guardians)  # cache prefetch in guardian

        # Return the first (and only, if exists) ChildGuardian object:
        return child_guardians[0] if len(child_guardians) > 0 else None

    def get_cache_ownerdelegate_delegate(self, delegate):
        """Returns the OwnerDelegate object of the user's delegate."""
        # Get the delegate's OwnerDelegate object for self owner user, either from a cached prefetch on owner/delegate
        # or by filtering ownerdelegate set.
        # Note: (owner, user) is unique in OwnerDelegate, therefore owner_delegates will return at most 1 result.
        owner = self
        owner_delegates = getattr(
            owner,
            'user_%s_delegate' % delegate.id,
            getattr(
                delegate,
                'user_%s_owner' % owner.id,
                owner.ownerdelegate_delegate_set.filter(user=delegate)
            )
        )
        owner_delegates = list(owner_delegates[:1])  # materialize and prefetch owner delegate (first only)
        setattr(owner, 'user_%s_delegate' % delegate.id, owner_delegates)  # cache prefetch in owner
        setattr(delegate, 'user_%s_owner' % owner.id, owner_delegates)  # cache prefetch in delegate

        # Return the first (and only, if exists) OwnerDelegate object:
        return owner_delegates[0] if len(owner_delegates) > 0 else None

    def get_cache_application_groups(self):
        """Returns list of application groups of the user."""
        # Get the application groups for the user, either from cache on user or by filtering the user groups.
        user = self
        # First try get from cache:
        app_groups = getattr(
            user,
            '_cache_app_groups',
            None
        )
        # If not in cache, then get it from database:
        if app_groups is None:
            from api.models import Lesson
            app_groups = Lesson.get_user_app_groups(user)  # get flat list of user app groups
            setattr(user, '_cache_app_groups', app_groups)  # cache in user
        return app_groups

    def get_cache_childguardian_child(self, child):
        """Returns the ChildGuardian object of the user's child."""
        # Note: This is reverse of IgniteUser.get_cache_childguardian_guardian.
        return child.get_cache_childguardian_guardian(self)

    def get_cache_ownerdelegate_owner(self, owner):
        """Returns the OwnerDelegate object of the user's owner."""
        # Note: This is reverse of IgniteUser.get_cache_ownerdelegate_delegate.
        return owner.get_cache_ownerdelegate_delegate(self)

    def get_cache_purchase_project(self, project):
        """Returns the Purchase object of the user for the project."""
        # Note: This is reverse of Project.get_cache_purchase_user.
        return project.get_cache_purchase_user(self)


class ChildGuardian(TimestampedModel):
    MODERATOR_PARENT = 'parent'
    MODERATOR_EDUCATOR = 'educator'
    MODERATOR_TYPE_CHOICES = [
        (MODERATOR_PARENT, 'Parent'),
        (MODERATOR_EDUCATOR, 'Educator'),
    ]

    MODERATOR_TYPES_TO_OXYGEN = {
        MODERATOR_PARENT: 'Parent',
        MODERATOR_EDUCATOR: 'Education',
    }
    MODERATOR_TYPES_FROM_OXYGEN = {val: key for key, val in MODERATOR_TYPES_TO_OXYGEN.items()}

    child = models.ForeignKey(IgniteUser, related_name='childguardian_guardian_set')
    guardian= models.ForeignKey(IgniteUser, related_name='childguardian_child_set')
    moderator_type = models.CharField(choices=MODERATOR_TYPE_CHOICES, max_length=50, default=MODERATOR_PARENT)

    class Meta:
        unique_together = (('child', 'guardian'),)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_auth_token(sender, instance=None, created=False, **kwargs):
    '''
    Generate an Auth Token on user creation
    '''

    if created:
        Token.objects.create(user=instance)
