from django.db import models
from django.db.models import Count
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.timezone import now as utc_now
from django_counter_field import CounterField
from jsonfield import JSONField

from utils_app.models import TimestampedModel

from .models import Step, Lesson, Project, Classroom
from api.emails import joined_classroom_email
from api.tasks import add_permissions_to_classroom_students


class StepState(TimestampedModel):
    """
    A state for a step of a user in a lesson
    """
    step         = models.ForeignKey(Step)
    lesson_state = models.ForeignKey('LessonState', related_name='step_states')
    state        = models.CharField(max_length=50, blank=True)
    user         = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='steps', null=True, blank=True)

    class Meta:
        unique_together = (('step', 'lesson_state'),)

    # Only save if this step is a part of the lesson
    def save(self, *args, **kwargs):
        super(StepState, self).save(*args, **kwargs)

        #Todo: send task to celery, to check if the lesson state should be marked as completed
        #get fresh lesson state object (to avoid prefetched cache):
        lesson_state = LessonState.objects.get(pk=self.lesson_state.pk)

        #calculate if lesson state is completed:
        viewed_steps = lesson_state.viewed_steps.count()
        number_of_steps_in_lessons = lesson_state.lesson.steps.count()
        lesson_state_completed = viewed_steps == number_of_steps_in_lessons

        #in case that lesson state is changed, then *update* (not .save) the project state:
        if lesson_state.is_completed != lesson_state_completed:
            # Note: Save only is_completed field of the state, in order not to truncate counters with older values.
            lesson_state.is_completed = lesson_state_completed
            lesson_state.save(update_fields=['is_completed'])

    def delete(self, using=None):
        super(StepState, self).delete(using)

        #get fresh lesson state object (to avoid prefetched cache):
        lesson_state = LessonState.objects.get(pk=self.lesson_state.pk)

        #mark the lesson state as not completed:
        if lesson_state.is_completed:
            # Note: Save only is_completed field of the state, in order not to truncate counters with older values.
            lesson_state.is_completed = False
            lesson_state.save(update_fields=['is_completed'])

    def __unicode__(self):
        return 'Step %s state %s' % (self.step, self.state)


class LessonState(TimestampedModel):
    """
    A state for a lesson of a user in a classroom/project.
    """
    lesson        = models.ForeignKey(Lesson, related_name='registrations')
    project_state = models.ForeignKey('ProjectState', related_name='lesson_states')
    is_completed  = models.BooleanField(default=False)
    viewed_steps  = models.ManyToManyField(Step, through=StepState)
    extra         = JSONField(help_text='Stores user specific data, e.g. canvas ID for Tinkercad', blank=True, null=True)
    user          = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='lessons', null=True, blank=True)

    class Meta:
        unique_together = (('project_state', 'lesson'),)
        ordering = ('lesson__project', 'lesson__order')

    def save(self, *args, **kwargs):
        """
        Checks whether the is_completed field was set and if so,
        modifies the is_completed of the relevant project as well.
        """
        if self.lesson.application in Lesson.STEPLESS_APPS:
            self.is_completed = True

        super(LessonState, self).save(*args, **kwargs)

        #get fresh project state object (to avoid prefetched cache):
        project_state = ProjectState.objects.get(pk=self.project_state.pk)

        #calculate if project state is completed:
        project_state_completed = False
        if self.is_completed:
            completed_lessons = project_state.lesson_states.filter(is_completed=True).count()
            number_of_lessons_in_project = project_state.project.lessons.count()
            project_state_completed = completed_lessons == number_of_lessons_in_project

        #in case that project state is changed, then *update* (not .save) the project state:
        if project_state.is_completed != project_state_completed:
            # Note: Save only is_completed field of the state, in order not to truncate counters with older values.
            project_state.is_completed = project_state_completed
            project_state.save(update_fields=['is_completed'])

    def delete(self, using=None):
        super(LessonState, self).delete(using)

        #get fresh project state object (to avoid prefetched cache):
        project_state = ProjectState.objects.get(pk=self.project_state.pk)

        #mark the project state as not completed:
        if project_state.is_completed:
            # Note: Save only is_completed field of the state, in order not to truncate counters with older values.
            project_state.is_completed = False
            project_state.save(update_fields=['is_completed'])

    def get_canvas_document_id(self):
        """
        Returns tuple of (document_id, is_init) of the canvas document id of the lesson state.
        If document_id is None, it means there is no personal canvas id for the user, and no init canvas id is defined.
        If is_init is True, it means the document id is initCanvasId of the lesson.
        If is_init is False, it means the document id is the personal canvas of the user.
        """
        # Try get the canvas document id from the 'extra' field:
        document_id = self.extra.get('canvasDocumentId', None) if self.extra else None
        is_init = document_id is None

        # Performance Note: This will probably happen once when the lesson state has not canvas document id,
        #                   and the loops iterate as long as not found the shared lessons group or document id in
        #                   the shared lessons states of the user.
        #                   Once the document_id is found, if it personal (found in shared lesson state), then
        #                   it is saved to the lesson state and it will not get into this process in further calls
        #                   for that lesson state.
        # If not exists, then try import it from the shared lessons group (defined on its project.extra):
        if document_id is None:
            project_extra = self.lesson.project.extra
            if project_extra:
                lessons_init = project_extra.get('lessonsInit', [])
                for lessons_group in lessons_init:
                    lessons_ids = lessons_group.get('lessonsIds', [])
                    # Found lessons init group that the lesson is part of:
                    if self.lesson.id in lessons_ids:
                        if lessons_ids:
                            shared_lessons_states = LessonState.objects.filter(
                                user = self.user,
                                lesson_id__in=[x for x in lessons_ids if x != self.lesson.id],
                            ).only('extra')
                            for shared_lesson_state in shared_lessons_states:
                                shared_lesson_state_extra = shared_lesson_state.extra or {}
                                # First attempt - try import it from shared lessons states:
                                document_id = shared_lesson_state_extra.get('canvasDocumentId', None)
                                # Set the personal shared canvas document id for this lesson state:
                                if document_id is not None:
                                    is_init = False  #personal canvas id
                                    self_extra = self.extra or {}
                                    self_extra['canvasDocumentId'] = document_id
                                    self.extra = self_extra
                                    self.save(update_fields=['extra'])
                                    break  #for shared_lesson_state in shared_lessons_states
                        # Second attempt - try import it from the shared lessons group init:
                        if document_id is None:
                            document_id = lessons_group.get('initCanvasId', None)
                            is_init = True  #init canvas id
                        break  #for lessons_group in lessons_init

        return (document_id, is_init)

    def get_canvas_external_params(self, update_params=None):
        # Get document id and whether it is init or personal:
        document_id, is_init = self.get_canvas_document_id()

        # Make external params to return
        params = update_params if update_params is not None else {}
        params.pop('edu-document-id', None)
        params.pop('edu-document-copy', None)
        if document_id is not None:
            params['edu-document-id'] = document_id
            if is_init:
                params['edu-document-copy'] = 'true'
        return params

    @classmethod
    def get_state_subject(cls):
        return 'lesson'

    def __unicode__(self):
        return 'Lesson %s for user %s' % (self.lesson, self.project_state.user)


class ProjectState(TimestampedModel):
    """
    A state for a project of a user.
    """
    project = models.ForeignKey(Project, related_name='registrations')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='projects')
    is_completed = models.BooleanField(default=False)
    viewed_lessons = models.ManyToManyField(Lesson, through=LessonState)

    # Counters
    enrolled_lessons_count = CounterField()
    completed_lessons_count = CounterField()

    class Meta:
        unique_together = (('user', 'project'),)

    @classmethod
    def get_state_subject(cls):
        return 'project'

    def __unicode__(self):
        return 'Project %s state for user %s' % (self.project, self.user)

    def get_lessons_states(self):
        '''Returns the lessons states for the project, ordered as the lessons in the project'''
        return self.lesson_states.all().order_by('lesson__order')

class ClassroomState(TimestampedModel):
    """
    A state for a classroom of a user.
    """
    APPROVED_STATUS = 'approved'
    PENDING_STATUS = 'pending'
    REJECTED_STATUS = 'rejected'
    STATUSES = (
        (APPROVED_STATUS, 'Approved'),
        (PENDING_STATUS, 'Pending'),
        (REJECTED_STATUS, 'Rejected'),
    )

    classroom = models.ForeignKey(Classroom, related_name='registrations')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='classrooms_states')
    status = models.CharField(choices=STATUSES, max_length=30, default=APPROVED_STATUS, help_text='User enroll status')

    # Counters
    # enrolled_projects_count = CounterField()
    # completed_projects_count = CounterField()

    class Meta:
        unique_together = (('user', 'classroom'),)

    @classmethod
    def get_state_subject(cls):
        return 'classroom'

    def __unicode__(self):
        return 'Classroom %s state for user %s' % (self.classroom, self.user)

    def get_projects_states(self):
        '''Returns the project states for the classroom'''

        return ProjectState.objects.filter(
            project__in=self.classroom.projects.all(),
            user=self.user
        )

    def __init__(self, *args, **kwargs):
        """Store the original value of status, in order to compare with saved value.

        See save() method for usage of __original_status."""
        super(ClassroomState, self).__init__(*args, **kwargs)
        self.__original_status = self.status
        self.__original_pk = self.pk

    def save(self, *args, **kwargs):
        """Saves ClassroomState and sends email notifications to moderators if necessary."""

        super(ClassroomState, self).save(*args, **kwargs)

        # Check if status of ClassroomState has changed to APPROVED_STATUS or 
        # if this is a new object created in the APPROVED_STATUS status.
        # And only for children.
        if (
            (self.status == self.APPROVED_STATUS) and 
            ((self.__original_status != self.APPROVED_STATUS) or (self.__original_pk is None))
            ):

            add_permissions_to_classroom_students.delay(self.classroom)

            if self.user.is_child:
                # Send email invites.
                joined_classroom_email(self)

        # Update "original" values
        self.__original_status = self.status
        self.__original_pk = self.pk
