from celery.task import task
import api.models


#region Delegated Tasks
@task()
def check_if_lesson_state_completed(lesson_state_id):
    # get fresh lesson state object (to avoid prefetched cache):
    lesson_state = api.models.LessonState.objects.get(pk=lesson_state_id)

    #calculate if lesson state is completed:
    viewed_steps = lesson_state.viewed_steps.count()
    number_of_steps_in_lessons = lesson_state.lesson.steps.count()
    lesson_state_completed = viewed_steps == number_of_steps_in_lessons

    #in case that lesson state is changed, then *update* (not .save) the project state:
    if lesson_state.is_completed != lesson_state_completed:
        # Note: Save only is_completed field of the state, in order not to truncate counters with older values.
        lesson_state.is_completed = lesson_state_completed
        lesson_state.save(update_fields=['is_completed'])
#endregion Delegated Tasks