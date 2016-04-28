import json

from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import Q, Count, Prefetch
from django.conf import settings
from django.conf.global_settings import LANGUAGES
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django_counter_field import CounterMixin, CounterField, connect_counter
from jsonfield import JSONField

from utils_app.models import TimestampedModel, DeleteStatusModel, GenericLinkedModel
from utils_app.hash import generate_code as generate_code_base
from utils_app.managers import DeleteStatusWithDraftManager, DeleteStatusWithDraftOriginsManager
from drafts.models import ChangeableDraftModel
import string

from .mixins import OrderedObjectInContainer
from .fields import TagsField, ArrayJSONField
from api.tasks import add_permissions_to_classroom_students, notify_and_mail_users

from marketplace.models import Purchase


class Review(TimestampedModel, DeleteStatusModel, GenericLinkedModel):
    """
    A generic review model, which could be linked to any other model.
    Currently we use it for Project, Lesson.
    """
    RATING_MIN = 1
    RATING_MAX = 10
    RATING_CHOICES = zip(range(RATING_MIN, RATING_MAX + 1), range(RATING_MIN, RATING_MAX + 1))

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='reviews')
    text = models.CharField(max_length=500)
    rating = models.IntegerField(choices=RATING_CHOICES)

    def __unicode__(self):
        return '%s/%s - %s (%s)' % (self.rating, self.RATING_MAX, self.text, self.owner)

    class Meta:
        unique_together = (('owner', 'content_type', 'object_id',),)


class PublishableModel(models.Model):

    PUBLISH_MODE_EDIT = 'edit'
    PUBLISH_MODE_REVIEW = 'review'
    PUBLISH_MODE_READY = 'ready'
    PUBLISH_MODE_PUBLISHED = 'published'
    PUBLISH_MODES = (
        (PUBLISH_MODE_EDIT, 'In Edit'),
        (PUBLISH_MODE_REVIEW, 'In Review'),
        (PUBLISH_MODE_READY, 'Ready For Publish'),
        (PUBLISH_MODE_PUBLISHED, 'Published'),
    )

    publish_mode = models.CharField(max_length=50, db_index=True, choices=PUBLISH_MODES, default=PUBLISH_MODE_EDIT)
    publish_date = models.DateTimeField(db_index=True, null=True, blank=True)
    min_publish_date = models.DateTimeField(db_index=True, null=True, blank=True)

    class Meta(object):
        abstract = True


class Classroom(TimestampedModel, DeleteStatusModel):
    '''
    A classroom based on a project, but with students and teachers.
    '''

    title = models.CharField(help_text='Classroom\'s title as it will be displayed to students', max_length=120)
    description = models.TextField(help_text='A short description of the classroom\'s goals and characteristics', blank=True, default='')
    banner_image = models.URLField(help_text='A URL of a cover picture for the classroom', blank=True, null=True, max_length=512)
    card_image = models.URLField(help_text='A URL of a card picture for the classroom', blank=True, null=True, max_length=512)

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='authored_classrooms')

    code = models.CharField(help_text='Classroom code for users to join the classroom', unique=True, blank=True, null=True, max_length=8)

    is_archived = models.BooleanField(help_text='Flag whether the classroom is archived', default=False)

    projects_separators = ArrayJSONField(JSONField(), blank=True, null=True)

    students = models.ManyToManyField(settings.AUTH_USER_MODEL, through='ClassroomState', related_name='classrooms')

    # Counters
    students_approved_count = CounterField()
    students_rejected_count = CounterField()
    students_pending_count = CounterField()

    projects_count = CounterField()

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('code', self.generate_code())  #by default, generate code if not set
        super(Classroom, self).__init__(*args, **kwargs)

    def __unicode__(self):
        return self.title

    @staticmethod
    def generate_code():
        return generate_code_base(8, chars=string.ascii_uppercase + string.digits)


# region Project
class Project(TimestampedModel, PublishableModel, DeleteStatusModel, ChangeableDraftModel):
    '''
    A project.

    A collection of lessons targeted at teaching a certain curriculum.
    '''

    # region Choices params
    EASY_DIFFICULTY = 'easy'
    MEDIUM_DIFFICULTY = 'intermediate'
    HARD_DIFFICULTY = 'hard'

    DIFFICULTIES = (
        (EASY_DIFFICULTY, 'Beginner'),
        (MEDIUM_DIFFICULTY, 'Intermediate'),
        (HARD_DIFFICULTY, 'Advanced'),
    )

    CC_BY_NC_SA_3_0 = 'CC-BY-NC-SA 3.0'
    CC_BY_SA_3_0 = 'CC-BY-SA 3.0'
    CC_BY_NC_3_0 = 'CC-BY-NC 3.0'
    CC_BY_3_0 = 'CC-BY 3.0'
    PUBLIC_DOMAIN = 'Public Domain'

    # NOTE: Make sure to put the default license to be first in the list of options.
    LICENSES = (
        (CC_BY_NC_SA_3_0, 'CC: Attribution-NonCommercial-ShareAlike 3.0 Unported'),
        (CC_BY_SA_3_0, 'CC: Attribution-ShareAlike 3.0 Unported'),
        (CC_BY_NC_3_0, 'CC: Attribution-NonCommercial 3.0 Unported'),
        (CC_BY_3_0, 'CC: Attribution 3.0 Unported'),
        (PUBLIC_DOMAIN, 'Public Domain'),
    )

    AGE_3_PLUS = '3+'
    AGE_6_PLUS = '6+'
    AGE_9_PLUS = '9+'
    AGE_12_PLUS = '12+'
    AGE_15_PLUS = '15+'
    AGE_18_PLUS = '18+'

    AGES = (
        (AGE_3_PLUS, '3+'),
        (AGE_6_PLUS, '6+'),
        (AGE_9_PLUS, '9+'),
        (AGE_12_PLUS, '12+'),
        (AGE_15_PLUS, '15+'),
        (AGE_18_PLUS, '18+'),
    )

    NO_LOCK = 0
    BUNDLED = 1
    LOCK_CHOICES = (
        (NO_LOCK, 'None'),
        (BUNDLED, 'Bundle'),
    )

    PERMS = {
        'EDIT': 'edit',
        'TEACH': 'teach',
        'VIEW': 'view',
        'PREVIEW': 'preview',
    }

    NGS_STANDARDS = (
        ("PS1", "Matter and Its Interactions"),
        ("PS2", "Motion and Stability: Forces and Interactions"),
        ("PS3", "Energy"),
        ("PS4", "Waves and Their Applications in Technologies for Information Transfer"),
        ("LS1", "From Molecules to Organisms: Structures and Processes"),
        ("LS2", "Ecosystems: Interactions, Energy, and Dynamics"),
        ("LS3", "Heredity: Inheritance and Variation of Traits"),
        ("LS4", "Biological Evolution: Unity and Diversity"),
        ("ESS1", "Earth's Place in the Universe"),
        ("ESS2", "Earth's Systems"),
        ("ESS3", "Earth and Human Activity"),
        ("ETS1", "Engineering Design"),
        ("ETS2", "Links Among Engineering, Technology, Science, and Society")
    )

    CCS_STANDARDS = (
        ("RL", "Reading Literature"),
        ("RI", "Reading Informational Text"),
        ("RF", "Reading Foundational Skills"),
        ("W", "Writing"),
        ("SL", "Speaking & Listening"),
        ("L", "Language"),
        ("RST", "Reading Science & Technical Subjects"),
        ("WHST", "Writing in History, Science, & Technical Subjects"),
        ("CC", "Counting and Cardinality"),
        ("OA", "Operations & Algebraic Thinking"),
        ("NBT", "Number & Operation in Base Ten"),
        ("NF", "Number & operations-Fractions"),
        ("MD", "Measurement and Data"),
        ("G", "Geometry"),
        ("RP", "Ratios and Proportional Relationships"),
        ("NS", "Number System"),
        ("EE", "Expressions and Equations"),
        ("F", "Functions"),
        ("SP", "Statistics and Probability"),
        ("MP", "Math Practices")
    )

    SUBJECTS = (
        ("art", "Art"),
        ("drama", "Drama"),
        ("geography", "Geography"),
        ("history", "History"),
        ("language arts", "Language Arts"),
        ("math", "Math"),
        ("music", "Music"),
        ("science", "Science"),
        ("social studies", "Social Studies"),
        ("technology", "Technology"),
    )

    TECHNOLOGY = (
        ("3d printing", "3D Printing"),
        ("electronics", "Electronics"),
        ("3d design", "3D Design"),
    )

    GRADES = (
        ("K", "K"),
        ("1", "1"),
        ("2", "2"),
        ("3", "3"),
        ("4", "4"),
        ("5", "5"),
        ("6", "6"),
        ("7", "7"),
        ("8", "8"),
        ("9", "9"),
        ("10", "10"),
        ("11", "11"),
        ("12", "12"),
    )
    # endregion Choices params

    title        = models.CharField(help_text='Project\'s title as it will be displayed to students', max_length=120)
    description  = models.TextField(help_text='A short description of the project\'s goals and characteristics', blank=True, default='')
    banner_image = models.URLField(help_text='A URL of a cover picture for the project', blank=True, null=True, max_length=512)
    card_image   = models.URLField(help_text='A URL of a card picture for the project', blank=True, null=True, max_length=512)

    duration   = models.PositiveIntegerField(help_text='The expected duration of the lesson in minutes', default=0)
    age        = models.CharField(choices=AGES, max_length=10, help_text='The required age', default=AGE_3_PLUS)
    difficulty = models.CharField(max_length=15, choices=DIFFICULTIES, help_text='Difficulty level', default=EASY_DIFFICULTY)
    license    = models.CharField(choices=LICENSES, max_length=30, help_text='The license that this project operates under', default=CC_BY_NC_SA_3_0)
    language   = models.CharField(help_text='Project\'s language', choices=LANGUAGES, max_length=50, default='en')

    lock         = models.IntegerField(choices=LOCK_CHOICES, default=NO_LOCK, help_text='A locked project is a project that only people with a certain permission can view/teach')
    lock_message = JSONField(help_text='A system message that explains why this project is locked', blank=True, default={})

    owner             = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='authored_projects')
    current_editor    = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='current_edit_projects', null=True, blank=True)

    # region Teacher info
    teachers_files_list = ArrayJSONField(JSONField(), blank=True, null=True)
    teacher_additional_resources = models.TextField(help_text='Information about the teacher who published the lesson', blank=True, default='')
    prerequisites = models.TextField(help_text='Course prerequisites', blank=True, null=True, default='', max_length=1000)
    teacher_tips = models.TextField(help_text='Tips for teachers', blank=True, null=True, default='', max_length=1000)

    ngss    = ArrayField(models.CharField(max_length=10, choices=NGS_STANDARDS), blank=True, null=True)
    ccss    = ArrayField(models.CharField(max_length=10, choices=CCS_STANDARDS), blank=True, null=True)
    subject = ArrayField(models.CharField(max_length=25, choices=SUBJECTS), blank=True, null=True)
    grades_range = ArrayField(models.CharField(max_length=10, choices=GRADES), blank=True, null=True)
    technology = ArrayField(models.CharField(max_length=25, choices=TECHNOLOGY), blank=True, null=True)

    four_cs_creativity = models.TextField(help_text='4 cs creativity', max_length=250, blank=True, null=True)
    four_cs_critical = models.TextField(help_text='4 cs critical', max_length=250, blank=True, null=True)
    four_cs_communication = models.TextField(help_text='4 cs communication', max_length=250, blank=True, null=True)
    four_cs_collaboration = models.TextField(help_text='4 cs collaboration', max_length=250, blank=True, null=True)
    skills_acquired = ArrayField(models.CharField(max_length=100), blank=True, null=True)
    learning_objectives = ArrayField(models.CharField(max_length=100), blank=True, null=True)
    # endregion Teacher info

    tags    = TagsField(max_length=150, blank=True, default='')
    reviews = GenericRelation(Review)

    extra   = JSONField(help_text='Extra data for the project and its lessons.', blank=True, null=True)

    is_searchable = models.BooleanField(help_text='Whether the object will be searchable in list of projects', default=True)

    # The classrooms that this project is a part of, or from the other perspective,
    # the projects in the classroom.
    classrooms = models.ManyToManyField(Classroom, through='ProjectInClassroom', related_name='projects')

    # Counters
    lesson_count   = CounterField()
    students_count = CounterField()

    # Define allowed fields to update in draft model and will be applied to origin object
    draft_writable_data_fields = ['title', 'description', 'banner_image', 'card_image', 'duration', 'age', 'difficulty',
                          'license', 'language', 'teachers_files_list', 'tags',
                          'ngss', 'ccss', 'prerequisites', 'teacher_tips',
                          'four_cs_creativity', 'four_cs_critical', 'four_cs_communication', 'four_cs_collaboration',
                          'teacher_additional_resources', 'teachers_files_list', 'skills_acquired',
                          'learning_objectives', 'grades_range', 'subject', 'technology',]
    # Define allowed fields to update in draft model but will not be applied to origin object
    draft_writable_meta_fields = ['publish_mode', 'current_editor',]
    # Define allowed fields to create in draft model but will not be updated after creation
    draft_create_fields = []

    # Make default manager to return active and origins (filter origins is needed since Project is stand-alone model)
    objects = DeleteStatusWithDraftOriginsManager()
    objects_with_drafts = DeleteStatusWithDraftManager()

    def __unicode__(self):
        return self.title

    @staticmethod
    def get_lessons_with_order_queryset(queryset=None, prefetch=('steps',)):
        """
        Returns the queryset needed for get_lessons_with_order.

        The reason that we export this functionality out of get_lessons_with_order
        is that we sometimes prepare the queryset beforehand, in the view
        function. This is done for optimization reasons. There's no reason
        for the view function to know the internals of the queryset and there's
        definitely no reason to write it twice (once for the view function, and
        the other time in case the flow of the program didn't go through the
        view function).
        """

        lessons_qs = queryset
        if lessons_qs == None:
            lessons_qs = Lesson.objects.all()

        return lessons_qs.select_related(
            'owner',
        ).prefetch_related(
            *prefetch
        ).annotate(
            number_of_students=Count('registrations')
        ).order_by('order')

    def __init__(self, *args, **kwargs):
        super(Project, self).__init__(*args, **kwargs)

        # keep tracking the publish_mode for doing something when publish_mode is changed and saved:
        self._init_publish_mode = self.publish_mode if self.pk else None

    def draft_get_or_create(self, draft_create_fields=None):
        # create the draft with publish_mode 'edit':
        draft_create_fields = draft_create_fields or {}
        draft_create_fields.update({
            'publish_mode': Project.PUBLISH_MODE_EDIT,
        })
        draft_obj, draft_created = super(Project, self).draft_get_or_create(draft_create_fields)

        # if draft was created, then make drafts for all of its lessons:
        if draft_created:
            for lesson in self.lessons.all():
                lesson.draft_get_or_create(draft_create_fields={
                    'project': draft_obj,
                })

        return draft_obj, draft_created

    def draft_discard(self, draft_delete_kwargs=None):
        # Note: Since lessons drafts are connected to project draft, the deleting the project draft deletes also lessons drafts.
        draft_delete_kwargs = draft_delete_kwargs or {}
        draft_delete_kwargs.update({
            'really_delete': True,
        })
        draft_discarded = super(Project, self).draft_discard(draft_delete_kwargs)
        return draft_discarded

    def get_lessons_with_order(self):
        '''
        Returned the lessons of this project, ordered, and with the field 'order'
        '''

        # See if there's already a "lessons_with_order" attribute on self.
        # If so, then all is good. If not, then fetch using
        # "get_lessons_with_order_queryset".
        lessons_with_order = getattr(self, 'lessons_with_order', None)
        if lessons_with_order is not None:
            return lessons_with_order
        else:
            return self.get_lessons_with_order_queryset(self.lessons.all())

    def save(self, *args, **kwargs):
        # first, really save the model:
        super(Project, self).save(*args, **kwargs)

        # current publish_mode was saved to db:
        update_fields = kwargs.get('update_fields')
        if update_fields is None or 'publish_mode' in update_fields:

            # re-set the init publish mode to the current saved:
            prev_publish_mode = self._init_publish_mode
            self._init_publish_mode = self.publish_mode

            # current publish_mode was changed to 'published':
            if self.publish_mode != prev_publish_mode and self.publish_mode == Project.PUBLISH_MODE_PUBLISHED:
                # automatically set the publish_date to updated time and save:
                self.publish_date = self.updated
                self.save(update_fields=['publish_date'], change_updated_field=False)

                # reset project states:
                self.registrations.all().delete()

    def delete(self, **kwargs):
        super(Project, self).delete(**kwargs)
        # If marked deleted and not published project:
        if self.pk and self.is_deleted and self.publish_mode != self.PUBLISH_MODE_PUBLISHED:
            # Delete all its user states:
            self.registrations.all().delete()
        # NOTE: If published project is deleted, then leave its states even when the project does not exist.
        #       It is like state exists, but content is unavailable.

    def get_permission_for_user(self, user, view_hash=None):
        """Get the permission that the user has over this object"""
        if self.can_edit(user):
            return self.PERMS['EDIT']
        if self.can_teach(user):
            return self.PERMS['TEACH']
        if self.can_view(user, view_hash):
            return self.PERMS['VIEW']
        if self.can_preview(user):
            return self.PERMS['PREVIEW']
        return None

    def get_cache_purchase_user(self, user):
        """Returns the Purchase object of the project for the user."""
        # Get the user's Purchase object for self project, either from a cached prefetch on project/user
        # or by filtering purchases set.
        # Note: (user, project) is unique in Purchase, therefore user_purchases will return at most 1 result.
        project = self
        user_purchases = getattr(
            project,
            'user_%s_purchases' % user.id,
            getattr(
                user,
                'project_%s_purchases' % project.id,
                project.purchases.filter(user=user)  # materialize queryset
            )
        )
        user_purchases = list(user_purchases[:1])  # materialize and prefetch user purchases (first only)
        setattr(project, 'user_%s_purchases' % user.id, user_purchases)  # cache prefetch in project
        setattr(user, 'project_%s_purchases' % project.id, user_purchases)  # cache prefetch in user

        # Return the first (and only, if exists) purchase:
        return user_purchases[0] if len(user_purchases) > 0 else None

    def is_editor(self, user):
        """Owners / Guardians (moderator) / Delegates (collaborators) / Super Users can always edit/teach (or view when in review mode)."""

        # Authenticated user.
        if user.is_authenticated():

            # super user
            if user.is_superuser:
                return True

            # owner
            owner = self.owner
            if owner == user:
                return True

            # delegate
            if owner.get_cache_ownerdelegate_delegate(user):
                return True

            # guardian (moderator)
            if owner.get_cache_childguardian_guardian(user):
                return True

        return False

    def is_reviewer(self, user):
        """Super Users are reviewers of projects."""

        # Authenticated user.
        if user.is_authenticated():

            # super user
            if user.is_superuser:
                return True

        return False

    def can_edit(self, user):
        """Whether allowed to edit project."""

        # If user can basically edit the project and it is in edit mode, then allow edit:
        if self.publish_mode == self.PUBLISH_MODE_EDIT:
            if self.is_editor(user):
                return True

        return False

    def can_teach(self, user):
        """Whether allowed to teach project."""

        # If origin project (not draft):
        if not self.is_draft:

            # Published project.
            if self.publish_mode == Project.PUBLISH_MODE_PUBLISHED:
                # Authenticated user.
                if user.is_authenticated():
                    # Locked project.
                    if self.lock != Project.NO_LOCK:
                        user_purchase = self.get_cache_purchase_user(user)
                        if user_purchase and user_purchase.permission == Purchase.TEACH_PERM:
                            return True
                    # Regular project.
                    else:
                        if not user.is_child:
                            return True

            # If user can basically edit the project and it is in published/ready mode, then allow teach:
            if self.publish_mode in [Project.PUBLISH_MODE_PUBLISHED, Project.PUBLISH_MODE_READY]:
                if self.is_editor(user):
                    return True

        return False

    def can_view(self, user, view_hash=None):
        """Whether allowed to view project."""

        # super user
        if user.is_superuser:
            return True

        # If origin project (not draft):
        if not self.is_draft:

            # Published project.
            if self.publish_mode == Project.PUBLISH_MODE_PUBLISHED:
                # Authenticated user.
                if user.is_authenticated():
                    # Locked project.
                    if self.lock != Project.NO_LOCK:
                        user_purchase = self.get_cache_purchase_user(user)
                        if user_purchase and user_purchase.permission in [Purchase.VIEW_PERM, Purchase.TEACH_PERM]:
                            return True
                    # Regular project.
                    else:
                        return True

            # If user has matching view hash key, then allow view (skip if draft):
            if view_hash and hasattr(self, 'view_invite') and self.view_invite.hash == view_hash:
                return True

        # If user can basically edit the project, then allow view:
        if self.is_editor(user):
            return True

        # If user has publish permission, then allow view:
        if self.can_publish(user):
            return True

        # If user is in any application group, then allow view:
        if user.is_authenticated():
            if len(user.get_cache_application_groups()) > 0:
                return True

        return False

    def can_preview(self, user, view_hash=None):
        """Whether allowed to preview project (meaning view with restricted fields)."""

        # If origin project (not draft):
        if not self.is_draft:

            # Published project.
            if self.publish_mode == self.PUBLISH_MODE_PUBLISHED:
                # Anyone can preview.
                return True

        # If user has view permission, then allow preview:
        if self.can_view(user, view_hash):
            return True

        return False

    def can_publish(self, user):
        """Whether allowed to publish project."""

        # Project in review or ready mode:
        if self.publish_mode in [self.PUBLISH_MODE_REVIEW, self.PUBLISH_MODE_READY]:
            # If user is superuser:
            if user.is_superuser:
                return True

        return False

    def can_reedit(self, user):
        """Whether allowed to return project back to edit mode."""

        # If user has publish permission, then allow re-edit:
        if self.can_publish(user):
            return True

        return False

    def can_create_draft(self, user):
        """Whether allowed to create project draft."""

        # Draft has no draft (call this method from the origin object):
        if self.is_draft:
            return False

        # Already has draft:
        if self.has_draft:
            return False

        # Draft can be created only for published project:
        if self.publish_mode != Project.PUBLISH_MODE_PUBLISHED:
            return False

        # Allow create draft if user can basically edit the project:
        if self.is_editor(user):
            return True

        return False

    def is_user_edit_locked(self, user, force_edit_from_id=None):
        return (
            self.current_editor and
            self.current_editor.id != user.id and
            self.current_editor.id != force_edit_from_id and
            force_edit_from_id != 0
        )

    def get_invite_permission_for_view(self, hash):
        return self.view_invite.hash == hash

    def notify_owner(self, notify_verb, notify_kwargs, include_recipient_delegates=True, send_mail_with_template=None):
        # If project is not saved, then skip notify.
        if not self.pk:
            return

        # Prepare recipients.
        recipients_q_params = models.Q(pk=self.owner.pk)  # owner
        if include_recipient_delegates:
            recipients_q_params |= models.Q(pk__in=self.owner.delegates.all())  # owner delegates
        recipients_qs = get_user_model().objects.filter(recipients_q_params)

        # Prepare notify kwargs.
        notify_kwargs['actor'] = self
        notify_kwargs['verb'] = notify_verb

        # Notify and optionally send mails to recipients:
        notify_and_mail_users.delay(
            recipients_qs,
            _mail_template=send_mail_with_template,
            **notify_kwargs
        )

    def validate_extra_field(self, value):
        """
        Validates the 'extra' field value, and returns the sanitized value.
        If not valid, ValueError exception is raised.
        """
        if value is not None and not isinstance(value, dict):
            raise ValueError('Expected "extra" value to be dict.')

        value = value or {}
        value_errors = {}

        # Validate extra 'lessonsInit' data:
        lessons_init = value.get('lessonsInit', None)
        if lessons_init:
            lessons_init_errors = []

            # Go over the lessons init groups and get the lessons ids.
            lessons_applications = {}
            for lessons_group in lessons_init:
                lessons_ids = lessons_group.get('lessonsIds', [])

                # Validate lessonsIds is a list:
                if not isinstance(lessons_ids, list):
                    lessons_init_errors.append('Expected "lessonsIds" to be a list.')
                    lessons_ids = None  #causes to remove the lessons group in the next step

                # Remove lessons group if not necessary (lessonsIds is empty):
                if not lessons_ids:
                    lessons_init.remove(lessons_group)
                    continue

                # Remove duplicates from lessonsIds:
                lessons_ids_set = set()
                lessons_ids = [x for x in lessons_ids if not (x in lessons_ids_set or lessons_ids_set.add(x))]
                lessons_group['lessonsIds'] = lessons_ids

                # Get the lessons ids and check that each lesson id appears in a single group.
                for lesson_id in lessons_ids:
                    try:
                        lesson_id = int(lesson_id)
                    except ValueError:
                        lessons_init_errors.append('Value "%s" is not a valid lesson ID.' % lesson_id)
                    else:
                        if lesson_id not in lessons_applications:
                            lessons_applications[lesson_id] = None
                        else:
                            lessons_init_errors.append('Lesson with ID "%s" appears in more than 1 group.' % lesson_id)

            # Get the lessons applications and check groups.
            if lessons_applications:
                # Get the lessons applications:
                lessons_applications_qs = self.lessons.only('application').filter(pk__in=lessons_applications.keys())
                for lesson_application in lessons_applications_qs:
                    lessons_applications[lesson_application.id] = lesson_application.application

                # Add errors for lessons that are not in the project.
                lessons_init_errors += [
                    'Lesson with ID "%s" is not found in the project.' % lesson_id
                    for lesson_id, application in lessons_applications.items() if application is None
                    ]

                # Check lessons groups are of the same application and remove not necessary groups.
                for lessons_group in lessons_init:
                    lessons_ids = lessons_group.get('lessonsIds', [])

                    # Remove lessons group if not necessary:
                    init_canvas_id = lessons_group.get('initCanvasId', None)
                    if init_canvas_id is None and len(lessons_ids) == 1:
                        lessons_init.remove(lessons_group)

                    # Set the application for the lessons group:
                    lessons_group_application = None
                    for lesson_id in lessons_ids:
                        lesson_application = lessons_applications.get(lesson_id)
                        if lesson_application != lessons_group_application:
                            if lessons_group_application is None:
                                lessons_group_application = lesson_application
                            elif lesson_application is not None:
                                lessons_init_errors.append('Lessons in the group %s are not of the same application.' % lessons_ids)
                                break
                    lessons_group['application'] = lessons_group_application

                    #TODO: validate initCanvasId for each application

            # If lessons init list is empty, then remove it:
            if not lessons_init:
                value.pop('lessonsInit', None)

            # if errors in lessonsInit:
            if lessons_init_errors:
                value_errors['lessonsInit'] = lessons_init_errors

        # Make extra to be None if nothing is set in it:
        if not value:
            value = None

        # if value errors, raise:
        if value_errors:
            raise ValueError(value_errors)

        return value
# endregion Project


# region Lesson
class Lesson(OrderedObjectInContainer, TimestampedModel, DeleteStatusModel, ChangeableDraftModel):
    '''
    A Lesson.
    '''

    APPLICATIONS = tuple([
        (settings.LESSON_APPS[app_key]['db_name'], settings.LESSON_APPS[app_key]['display_name'])
        for app_key in settings.LESSON_APPS_ORDER  #use constant apps order to prevent unnecessary migrations
    ])

    ENABLED_APPLICATIONS = tuple([
        (settings.LESSON_APPS[app_key]['db_name'], settings.LESSON_APPS[app_key]['display_name'])
        for app_key in settings.LESSON_APPS_ORDER if settings.LESSON_APPS[app_key]['enabled']
    ])

    STEPLESS_APPS = [
        settings.LESSON_APPS[app_name]['db_name'] for app_name in ['Instructables', 'Video']
    ]

    title = models.CharField(help_text='Lesson\'s title as it will be displayed to users', max_length=120)

    duration = models.PositiveIntegerField(help_text='The expected duration of the lesson in minutes', default=0)

    application = models.CharField(choices=APPLICATIONS, help_text='The application that the lesson takes place at', max_length=50)
    application_blob = JSONField(help_text='A JSON field that stores application specific data for presenting this step. It\'s recommended to use a URL', blank=True, default={})

    # The project this lesson is part of and its order location in the list of lessons in the project:
    project = models.ForeignKey(Project, related_name='lessons')
    order = models.IntegerField(db_index=True, null=False)

    # Counters
    steps_count = CounterField()
    students_count = CounterField()

    # Define allowed fields to update in draft model
    draft_writable_data_fields = ['title', 'duration',]
    # Define allowed fields to create in draft model but will not be updated after creation
    draft_create_fields = ['project',]

    # Make default manager to return active (filter origins is not needed since Lesson is part of Project model)
    objects = DeleteStatusWithDraftManager()

    class Meta:
        # Custom Migration: partial unique together on (project, order) where is_deleted=FALSE.
        index_together = (('project', 'order'),)  #partial index, where is_deleted=FALSE
        ordering = ('project', 'order')

    class OrderedObjectInContainerSettings:
        order_field = 'order'
        ordered_key_field = None
        container_key_field = 'project'

    def __unicode__(self):
        return self.title

    @classmethod
    def get_user_app_groups(cls, user, return_queryset=False):
        '''
        Returns list of all application groups the user is member of.
        By default returns list of app groups names, and can return queryset when return_queryset is True.
        '''
        apps = [a for a,_ in cls.APPLICATIONS]
        user_apps = user.groups.filter(name__in=apps)
        if return_queryset:
            return user_apps
        return list(user_apps.values_list('name', flat=True))

    def delete(self, **kwargs):
        super(Lesson, self).delete(**kwargs)
        # If marked deleted and not lesson of published project:
        if self.pk and self.is_deleted and self.project.publish_mode != Project.PUBLISH_MODE_PUBLISHED:
            # Delete all its user states:
            self.registrations.all().delete()

    def draft_get_or_create(self, draft_create_fields=None):
        draft_project = self.project.draft_get()
        # if draft project exists - create drafts beneath:
        if draft_project:
            # create lesson draft connected to project draft:
            draft_create_fields = draft_create_fields or {}
            draft_create_fields.update({
                'project': draft_project,
            })
            draft_obj, draft_created = super(Lesson, self).draft_get_or_create(draft_create_fields)
            # if draft was created, then make drafts for all of its steps:
            if draft_created:
                for step in self.steps.all():
                    step.draft_get_or_create()
        # otherwise, if draft project doesn't exist - create drafts for the project:
        else:
            self.project.draft_get_or_create()
            if hasattr(self, '_draft_object_cache'):
                delattr(self, '_draft_object_cache')  # delete cached draft_object to force reloading it from db
            draft_obj, draft_created = self.draft_get(), True

        return draft_obj, draft_created

    def draft_discard(self, draft_delete_kwargs=None):
        # Do not allow discard only lesson draft - discard the whole project draft
        return False

    def copy_lesson_steps(self, to_lesson):
        base_steps = self.steps.all()
        new_steps = [Step(
            order=step.order,
            title=step.title,
            description=step.description,
            image=step.image,
            application_blob=step.application_blob,
            instructions_list=step.instructions_list,
            lesson=to_lesson
        ) for step in base_steps]
        Step.objects.bulk_create(new_steps)

    def copy_lesson_to_project(self, to_project):
        new_lesson = Lesson.objects.create(
            project=to_project,
            title=self.title,
            duration=self.duration,
            application=self.application,
            application_blob=self.application_blob,
            steps_count=self.steps_count
        )
        self.copy_lesson_steps(new_lesson)
        return new_lesson

    def change_parent_updated_field(self, updated=None):
        self._change_updated_field_for_parent(self.project, updated)
# endregion Lesson


class Step(OrderedObjectInContainer, TimestampedModel, DeleteStatusModel, ChangeableDraftModel):
    '''
    A single lesson step.
    '''
    VIDEO_STEP_TYPE = 1
    LECTURE_STEP_TYPE = 2

    order = models.IntegerField(help_text='The step number', db_index=True, null=False)
    title = models.CharField(help_text='The title as it will appear to the user', max_length=120)
    description = models.TextField(help_text='A short description', blank=True, default='')
    image = models.URLField(help_text='A URL of an image that will accompany the step', blank=True, null=True)
    # hint = models.TextField(help_text='A hint to help complete the step', default='', blank=True)
    application_blob = JSONField(help_text='A JSON field that stores application specific data for presenting this step. It\'s recommended to use a URL', blank=True, default={})

    lesson = models.ForeignKey('Lesson', related_name='steps')

    # Instructions
    instructions_list = ArrayJSONField(JSONField(), blank=True, null=True)

    # Define allowed fields to update in draft model
    draft_writable_data_fields = ['title', 'description', 'image', 'instructions_list',]
    # Define allowed fields to create in draft model but will not be updated after creation
    draft_create_fields = ['lesson',]

    # Make default manager to return active (filter origins is not needed since Step is part of Lesson model)
    objects = DeleteStatusWithDraftManager()

    class Meta:
        # Custom Migration: partial unique together on (lesson, order) where is_deleted=FALSE.
        index_together = (('lesson', 'order'),)  #partial index, where is_deleted=FALSE
        ordering = ('lesson', 'order',)

    class OrderedObjectInContainerSettings:
        order_field = 'order'
        ordered_key_field = None
        container_key_field = 'lesson'

    def __unicode__(self):
        return '%(lesson)s (%(order)s): %(step)s' % dict({
            'lesson': self.lesson.title,
            'order': self.order,
            'step': self.title,
        })

    def delete(self, **kwargs):
        super(Step, self).delete(**kwargs)
        # If marked deleted and not step of lesson of published project:
        if self.pk and self.is_deleted and self.lesson.project.publish_mode != Project.PUBLISH_MODE_PUBLISHED :
            # Delete all its user states:
            self.stepstate_set.all().delete()

    def draft_get_or_create(self, draft_create_fields=None):
        draft_lesson = self.lesson.draft_get()
        # if draft lesson exists - create drafts beneath:
        if draft_lesson:
            draft_create_fields = draft_create_fields or {}
            draft_create_fields.update({
                'lesson': draft_lesson,
            })
            draft_obj, draft_created = super(Step, self).draft_get_or_create(draft_create_fields)
        # otherwise, if draft lesson doesn't exist - create drafts for the lesson:
        else:
            self.lesson.draft_get_or_create()
            if hasattr(self, '_draft_object_cache'):
                delattr(self, '_draft_object_cache')  # delete cached draft_object to force reloading it from db
            draft_obj, draft_created = self.draft_get(), True

        return draft_obj, draft_created

    def draft_discard(self, draft_delete_kwargs=None):
        # Do not allow discard only step draft - discard the whole project draft
        return False

    def change_parent_updated_field(self, updated=None):
        self._change_updated_field_for_parent(self.lesson, updated)


class ProjectInClassroom(OrderedObjectInContainer, TimestampedModel):
    '''
    A ManyToMany Relationship field between Project and Classroom.
    '''

    project = models.ForeignKey(Project)
    classroom = models.ForeignKey(Classroom, related_name='projects_through_set')

    order = models.IntegerField(help_text='The order in which the project should be taken in the classroom', db_index=True, null=False)

    class Meta:
        unique_together = (('project', 'classroom'), ('classroom', 'order'),)
        ordering = ['classroom', 'order']

    class OrderedObjectInContainerSettings:
        order_field = 'order'
        ordered_key_field = 'project'
        container_key_field = 'classroom'

    def save(self, *args, **kwargs):

        ret = super(ProjectInClassroom, self).save(*args, **kwargs)

        # If a locked project is added to the classroom, update purchases
        if self.project.lock != Project.NO_LOCK:
            add_permissions_to_classroom_students.delay(self.classroom)

        return ret


class ProjectGroup(models.Model):
    group_name = models.CharField(max_length=15, unique=True)
    projects = ArrayField(models.IntegerField(verbose_name='Projects IDs'))

    def get_projects(self):
        projects = cache.get('project_group_%s' % self.group_name)
        if projects is None:
            projects =self.add_projects_to_cache()
        return projects

    def add_projects_to_cache(self):
        projects = self.projects
        cache.set('project_group_%s' % self.group_name, projects)
        return projects

    def save(self, *args, **kwargs):
        if self.pk:
            # invalidate to old cache
            orig_obj = ProjectGroup.objects.get(pk=self.pk)
            cache.delete_pattern('project_group_%s' % orig_obj.group_name)
        group = super(ProjectGroup, self).save(*args, **kwargs)
        self.add_projects_to_cache()
        return group

    @classmethod
    def get_projects_by_group_name(cls, group_name):
        projects = cache.get('project_group_%s' % group_name)

        # If not found in cache, try fetch them from database (also puts in cache):
        if projects is None:
            try:
                project_group_obj = cls.objects.get(group_name=group_name)
            except cls.DoesNotExist:
                return None
            projects = project_group_obj.get_projects()

        return projects
