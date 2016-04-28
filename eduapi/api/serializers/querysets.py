from django.db.models import QuerySet, Prefetch

from utils_app.counter import ExtendQuerySetWithSubRelated

from api.models import (
    Lesson,
    Project,
    Classroom,
    ProjectInClassroom,
    LessonState,
    ProjectState,
    ClassroomState,
    Step,
    Purchase,
    OwnerDelegate,
    ChildGuardian,
)


### Optimization Note:
### ------------------
### In current Django version (1.7.7), doing Prefetch inside Prefetch causes the inner prefetch queryset to run twice!
### More over, Prefetch queryset that has select_related of the current model does JOIN to the model table, even this
### JOIN is not needed, since the current model is already fetched and prefetched objects are automatically connected to it.
###
### Thus, we use optimize_for_serializer(default=False) for Prefetch querysets that has in their optimize default any use of
### prefetch_related and/or select_related that is not the current model. And then add the select_related and
### prefetch_related used with default=True manually to the Prefetch queryset.
###
### [If newer versions of Django will avoid those 2 issues mentioned above, then it is possible to use default=True
### also for Prefetch querysets, just make sure to remove the manually added select_related and prefetch_related.]


def optimize_for_serializer_lesson_state(queryset, default=True, with_counters=False):
    queryset = queryset.all()

    #optimize default:
    if default:
        queryset = queryset.select_related(
            'lesson',
            'project_state',
            'project_state__user',
        )
        queryset = queryset.prefetch_related(
            'viewed_steps',
        )

    return queryset


def optimize_for_serializer_project_state(queryset, default=True, embed_list=None, with_counters=False):
    embed_list = embed_list or []
    queryset = queryset.all()

    #optimze default:
    if default:
        queryset = queryset.select_related(
            'project',
            'user',
        )

    #optimize with embed:
    if 'lessonStates' in embed_list:
        lesson_states_queryset = optimize_for_serializer_lesson_state(LessonState.objects.all(), default=False, with_counters=True)\
            .select_related('lesson')
        queryset = queryset.prefetch_related(
            Prefetch(
                'lesson_states',
                queryset=lesson_states_queryset,
            ),
            'lesson_states__viewed_steps'
        )

    return queryset


def optimize_for_serializer_classroom_state(queryset, default=True, with_counters=False):
    queryset = queryset.all()

    #optimize default:
    if default:
        queryset = queryset.select_related(
            'classroom',
            'classroom__owner',
            'user',
        )

    #optimize with counters:
    if with_counters:
        #add counters:
        classroomstate_user_field = ClassroomState._meta.get_field_by_name('user')[0]
        projectstate_user_field = ProjectState._meta.get_field_by_name('user')[0]
        classrooms_user_qs = Classroom.objects.extra(
            where=[
                '"%(projectstate_table)s"."%(projectstate_field)s"="%(classroomstate_table)s"."%(classroomstate_field)s"' % {
                    'projectstate_table': projectstate_user_field.model._meta.db_table,
                    'projectstate_field': projectstate_user_field.attname,
                    'classroomstate_table': classroomstate_user_field.model._meta.db_table,
                    'classroomstate_field': classroomstate_user_field.attname,
                }
            ]
        )
        queryset = ExtendQuerySetWithSubRelated(queryset)
        # queryset = queryset.add_counter('number_of_classroom_projects', 'classroom', None, 'projects')
        queryset = queryset.add_counter('number_of_enrolled_projects', 'classroom', classrooms_user_qs, 'projects__registrations')
        queryset = queryset.add_counter('number_of_completed_projects', 'classroom', classrooms_user_qs.filter(projects__registrations__is_completed=True), 'projects__registrations')

    return queryset


def optimize_for_serializer_step(queryset, default=True, embed_list=None):
    queryset = queryset.all()

    #optimize default:
    if default:
        queryset = queryset.select_related(
            'lesson'
        )

    #optimize with embed:
    if 'draft' in embed_list:
        queryset = queryset.prefetch_related(
            'draft_object',
        )
    if 'origin' in embed_list:
        queryset = queryset.select_related(
            'draft_origin',
        )

    return queryset


def optimize_for_serializer_lesson(queryset, default=True, embed_list=None, embed_user=None, with_counters=False):
    embed_list = embed_list or []
    queryset = queryset.all()

    #optimize default:
    if default:
        queryset = queryset.select_related(
            'project',
            'project__owner',
        )

    #optimize with embed:
    if 'steps' in embed_list:
        step_optimized_queryset = optimize_for_serializer_step(Step.objects.all(), default=False, embed_list=embed_list)
        queryset = queryset.prefetch_related(
            Prefetch(
                'steps',
                queryset=step_optimized_queryset,
            ),
        )
    elif 'stepsIds' in embed_list:
        queryset = queryset.prefetch_related(
            'steps'
        )
    if 'draft' in embed_list:
        queryset = queryset.prefetch_related(
            'draft_object',
        )
    if 'origin' in embed_list:
        queryset = queryset.select_related(
            'draft_origin',
        )

    #optimize with embed_user:
    if embed_user:
        user_registration_queryset = optimize_for_serializer_lesson_state(LessonState.objects.filter(project_state__user=embed_user), default=False, with_counters=True)\
            .select_related('project_state', 'project_state__user')
        queryset = queryset.prefetch_related(
            Prefetch(
                'registrations',
                queryset=user_registration_queryset,
                to_attr='user_registration'
            ),
            'user_registration__viewed_steps',
        )

    return queryset


def optimize_for_serializer_project(queryset, default=True, user=None, embed_list=None, embed_user=None, with_counters=False, with_order=False, with_permissions=False):
    embed_list = embed_list or []
    queryset = queryset.all()

    #optimize default:
    if default:
        queryset = queryset.select_related(
            'owner',
            'current_editor',
        )

    #optimize with embed:
    if 'lessons' in embed_list:
        lesson_optimized_queryset = optimize_for_serializer_lesson(Lesson.objects.all(), default=False, embed_list=embed_list, with_counters=True)
        queryset = queryset.prefetch_related(
            Prefetch(
                'lessons',
                queryset=lesson_optimized_queryset,
            ),
        )
    elif 'lessonsIds' in embed_list:
        queryset = queryset.prefetch_related(
            'lessons',
        )
    if 'draft' in embed_list:
        queryset = queryset.prefetch_related(
            'draft_object',
        )
    if 'origin' in embed_list:
        queryset = queryset.select_related(
            'draft_origin',
        )

    #optimize with embed_user:
    if embed_user:
        user_registration_queryset = optimize_for_serializer_project_state(ProjectState.objects.filter(user=embed_user), default=False, with_counters=True)\
            .select_related('user')
        queryset = queryset.prefetch_related(
            Prefetch(
                'registrations',
                queryset=user_registration_queryset,
                to_attr='user_registration'
            ),
        )

    #optimize with order:
    if with_order:
        #add order field, and sort by (classroom, order):
        queryset = queryset\
            .extra(select={'order': ProjectInClassroom._meta.db_table+'.order'})\
            .order_by('projectinclassroom__classroom', 'projectinclassroom__order')

    #optimize with permissions (based on 'user' argument):
    if with_permissions and user and user.is_authenticated():
        queryset = queryset.prefetch_related(
            Prefetch(
                'purchases',
                queryset=Purchase.objects.filter(user=user),
                #Note: make sure to use the same cache key as in Project.get_cache_purchase_user() method.
                to_attr='user_%s_purchases' % user.id,
            ),
            Prefetch(
                'owner__ownerdelegate_delegate_set',
                queryset=OwnerDelegate.objects.filter(user=user),
                #Note: make sure to use the same cache key as in IgniteUser.get_cache_ownerdelegate_delegate() method.
                to_attr='user_%s_delegate' % user.id,
            ),
            Prefetch(
                'owner__childguardian_guardian_set',
                queryset=ChildGuardian.objects.filter(guardian=user),
                #Note: make sure to use the same cache key as in IgniteUser.get_cache_childguardian_guardian() method.
                to_attr='user_%s_guardian' % user.id,
            ),
        )

    return queryset


def optimize_for_serializer_classroom(queryset, default=True, embed_list=None, embed_user=None, with_counters=False):
    embed_list = embed_list or []
    queryset = queryset.all()

    #optimize default:
    if default:
        queryset = queryset.select_related(
            'owner',
        )

    #optimize with embed:
    ordered_projects_for_classroom_queryset = Project.objects.all().order_by('projectinclassroom__classroom', 'projectinclassroom__order')
    if 'projects' in embed_list:
        projects_prefetch_queryset = optimize_for_serializer_project(ordered_projects_for_classroom_queryset, default=False, with_counters=True, with_order=True)\
            .select_related('owner')
        queryset = queryset.prefetch_related(
            Prefetch(
                'projects',
                queryset=projects_prefetch_queryset,
                to_attr='projects_ordered_list',
            ),
        )
    elif 'projectsIds' in embed_list:
        queryset = queryset.prefetch_related(
            Prefetch(
                'projects',
                queryset=ordered_projects_for_classroom_queryset,
                to_attr='projects_ordered_list',
            ),
        )

    #optimize with embed_user:
    if embed_user:
        user_registration_queryset = optimize_for_serializer_classroom_state(ClassroomState.objects.filter(user=embed_user), default=False, with_counters=True)\
            .select_related('user')
        queryset = queryset.prefetch_related(
            Prefetch(
                'registrations',
                queryset=user_registration_queryset,
                to_attr='user_registration'
            ),
        )

    return queryset


def optimize_for_serializer_review(queryset, default=True):
    queryset = queryset.all()

    #optimize default:
    if default:
        queryset = queryset.select_related(
            'content_type',
            'owner',
        )

    return queryset


def optimize_for_serializer_classroom_student(queryset, default=True, with_student_status=False, student_classroom_states_queryset=None):
    queryset = queryset.all()

    #optimize default:
    if default:
        pass

    #optimize with student status:
    if with_student_status:
        #add classroom-state status field as 'student_status' field:
        #Note: (classroom, user) is unique in ClassroomState, thus each student in the list have a single classroom-state status.
        queryset = queryset.extra(
            select={
                'student_status': '"%s"."%s"' % (ClassroomState._meta.db_table, ClassroomState._meta.get_field_by_name('status')[0].attname,),
            },
        )

    #optimize with classroom states:
    if student_classroom_states_queryset is not None:
        my_students_classrooms_states_prefetch_queryset = optimize_for_serializer_classroom_state(student_classroom_states_queryset, with_counters=True)
        queryset = queryset.prefetch_related(
            Prefetch(
                'classrooms_states',
                queryset=my_students_classrooms_states_prefetch_queryset,
                to_attr='student_classrooms_states'
            ),
        )

    return queryset
