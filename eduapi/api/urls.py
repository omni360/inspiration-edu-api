from django.conf.urls import patterns, url, include
from api.views.notification_views import NotificationsList, UnreadNotificationsList, ReadNotificationsList, \
    UnreadNotificationsDetail, RereadNotificationsDetail

from .auth.views import ObtainApiAuthToken, ResetOxygenPassword
from states.views import StepStateCreate, StepStateDelete, LessonStart

from .views import (
    ApiRoot,

    LessonList,
    LessonDetail,
    LessonListOnlyGet,
    LessonDetailOnlyGet,

    ProjectList,
    ProjectDetail,
    ProjectModeDetail,
    ProjectProjectStateList,
    ProjectProjectStateDetail,
    ProjectReviewList,
    ProjectReviewDetail,
    ProjectLessonStepDetail,
    ProjectLessonStateList,
    ProjectLessonStateDetail,

    ClassroomList,
    ClassroomDetail,
    ClassroomClassroomStateList,
    ClassroomClassroomStateDetail,
    ClassroomProjectList,
    ClassroomProjectDetail,
    ClassroomProjectStateList,
    ClassroomProjectStateDetail,
    ClassroomStudentsList,
    ClassroomStudentsDetail,
    ClassroomCodeGeneratorDetail,
    ClassroomCodeInviteList,
    ClassroomCodeDetail,
    ClassroomCodeStateDetail,

    ProjectDraftDetail,
    LessonDraftList,
    LessonDraftDetail,
    ProjectLessonStepDraftList,
    ProjectLessonStepDraftDetail,
    ProjectDraftModeDetail,

    CurrentUser,
    UserList,
    UserDetail,
    UserActivity,
    UserClassroomStateList,
    UserClassroomStateDetail,
    UserProjectStateList,
    UserProjectStateDetail,
    UserLessonStateDetail,
    UserClassroomProjectStateList,
    UserClassroomProjectStateDetail,
    UserProjectLessonStateList,
    UserProjectLessonStateDetail,
    UserReviewList,
    UserReviewDetail,
    CurrentUserChildrenList,
    CurrentUserChildrenDetails,
    CurrentUserStudentsList,
    CurrentUserStudentsDetail,
    CurrentUserUsersList,
    CurrentUserUsersDetail,
    CurrentUserDelegateList,
    CurrentUserDelegateDetail,
    CurrentUserDelegatorList,
    CurrentUserDelegatorDetail,
    InviterDelegateInviteList,

    VerifyAdulthood,

    InviteeDelegateInviteDetail,

    ProjectLessonStepList, LessonCopyDetail,
    ViewInviteDetail)

from marketplace.views import MarketplaceCallbacks

lesson_urls = patterns('',
    url(r'^/(?P<pk>\d+)/$', LessonDetailOnlyGet.as_view(), name='lesson-detail'),
    url(r'^/$', LessonListOnlyGet.as_view(), name='lesson-list'),
)

project_urls = patterns('',
    url(r'^/(?P<pk>\d+)/$', ProjectDetail.as_view(), name='project-detail'),
    url(r'^/(?P<project_id>\d+)/view_invitation/$', ViewInviteDetail.as_view(), name='view-invite-detail'),
    url(r'^/(?P<project_pk>\d+)/mode/$', ProjectModeDetail.as_view(), name='project-mode-detail'),  #->/mode/
    url(r'^/$', ProjectList.as_view(), name='project-list'),

    # Project -> State
    url(r'^/state/$', ProjectProjectStateList.as_view(), name='project-state-list'),
    url(r'^/(?P<project_pk>\d+)/state/$', ProjectProjectStateDetail.as_view(), name='project-state-detail'),

    # Project -> Draft
    url(r'^/(?P<project_pk>\d+)/draft/$', ProjectDraftDetail.as_view(), name='project-draft-detail'),
    url(r'^/(?P<project_pk>\d+)/lessons/draft/$', LessonDraftList.as_view(), name='project-lesson-draft-list'),
    url(r'^/(?P<project_pk>\d+)/lessons/(?P<lesson_pk>\d+)/draft/$', LessonDraftDetail.as_view(), name='project-lesson-draft-detail'),
    url(r'^/(?P<project_pk>\d+)/lessons/(?P<lesson_pk>\d+)/steps/draft/$', ProjectLessonStepDraftList.as_view(), name='project-lesson-step-draft-list'),
    url(r'^/(?P<project_pk>\d+)/lessons/(?P<lesson_pk>\d+)/steps/(?P<order>\d+)/draft/$', ProjectLessonStepDraftDetail.as_view(), name='project-lesson-step-draft-detail'),
    url(r'^/(?P<project_pk>\d+)/draft/mode/$', ProjectDraftModeDetail.as_view(), name='project-draft-mode-detail'),  #->/draft/mode/

    # Project -> Reviews
    url(r'^/(?P<project_pk>\d+)/reviews/$', ProjectReviewList.as_view(), name='project-review-list'),
    url(r'^/(?P<project_pk>\d+)/reviews/(?P<pk>\d+)/$', ProjectReviewDetail.as_view(), name='project-review-detail'),

    # Project -> Lesson
    url(r'^/(?P<project_pk>\d+)/lessons/$', LessonList.as_view(), name='project-lesson-list'),
    url(r'^/(?P<project_pk>\d+)/lessons/(?P<pk>\d+)/$', LessonDetail.as_view(), name='project-lesson-detail'),
    url(r'^/(?P<project_pk>\d+)/lessons/copy/$', LessonCopyDetail.as_view(), name='project-lesson-copy'),
    # Project -> Lesson -> Steps
    url(r'^/(?P<project_pk>\d+)/lessons/(?P<lesson_pk>\d+)/steps/(?P<order>\d+)/$', ProjectLessonStepDetail.as_view(), name='project-lesson-step-detail'),
    url(r'^/(?P<project_pk>\d+)/lessons/(?P<lesson_pk>\d+)/steps/$', ProjectLessonStepList.as_view(), name='project-lesson-step-list'),
    # Project -> Lesson -> Step -> States
    url(r'^/(?P<project_pk>\d+)/lessons/(?P<lesson_pk>\d+)/start/$', LessonStart.as_view(), name='lesson-start'),
    url(r'^/(?P<project_pk>\d+)/lessons/(?P<lesson_pk>\d+)/steps/state/$', StepStateCreate.as_view(), name='step-state-create'),
    url(r'^/(?P<project_pk>\d+)/lessons/(?P<lesson_pk>\d+)/steps/(?P<order>\d+)/state/$', StepStateDelete.as_view(), name='step-state-delete'),
    # Project -> Lesson -> State    TODO: the next two are not in use (depricated?)
    url(r'^/(?P<project_pk>\d+)/lessons/state/$', ProjectLessonStateList.as_view(), name='project-lesson-state-list'),
    url(r'^/(?P<project_pk>\d+)/lessons/(?P<lesson_pk>\d+)/state/$', ProjectLessonStateDetail.as_view(), name='project-lesson-state-detail'),
)

classroom_urls = patterns('',
    url(r'^/(?P<pk>\d+)/$', ClassroomDetail.as_view(), name='classroom-detail'),
    url(r'^/$', ClassroomList.as_view(), name='classroom-list'),

    # Classroom -> State
    url(r'^/state/$', ClassroomClassroomStateList.as_view(), name='classroom-state-list'),
    url(r'^/(?P<classroom_pk>\d+)/state/$', ClassroomClassroomStateDetail.as_view(), name='classroom-state-detail'),

    # Classroom -> Projects -> State    TODO: not in use (embed=lessonStates is used instead)
    url(r'^/(?P<classroom_pk>\d+)/projects/state/$', ClassroomProjectStateList.as_view(), name='classroom-project-state-list'),
    url(r'^/(?P<classroom_pk>\d+)/projects/(?P<project_pk>\d+)/state/$', ClassroomProjectStateDetail.as_view(), name='classroom-project-state-detail'),

    # Classroom -> Projects
    url(r'^/(?P<classroom_pk>\d+)/projects/$', ClassroomProjectList.as_view(), name='classroom-project-list'),
    url(r'^/(?P<classroom_pk>\d+)/projects/(?P<pk>\d+)/$', ClassroomProjectDetail.as_view(), name='classroom-project-detail'),

    # Classroom -> Students
    url(r'^/(?P<classroom_pk>\d+)/students/$', ClassroomStudentsList.as_view(), name='classroom-students-list'),
    url(r'^/(?P<classroom_pk>\d+)/students/(?P<pk>\d+)/$', ClassroomStudentsDetail.as_view(), name='classroom-students-detail'),

    # Classroom -> Code
    url(r'^/(?P<classroom_pk>\d+)/code/$', ClassroomCodeGeneratorDetail.as_view(), name='classroom-code-generator-detail'),
    url(r'^/(?P<classroom_pk>\d+)/code/invite/$', ClassroomCodeInviteList.as_view(), name='classroom-code-invite-list'),
    url(r'^/code/(?P<classroom_code>[a-zA-Z0-9]{8})/$', ClassroomCodeDetail.as_view(), name='classroom-code-detail'),
    url(r'^/code/(?P<classroom_code>[a-zA-Z0-9]{8})/state/$', ClassroomCodeStateDetail.as_view(), name='classroom-code-state-detail'),
)

auth_urls = patterns('',
    url(r'^/get-token/$', ObtainApiAuthToken.as_view(), name='get-auth-token'),
    url(r'^/get-token/(?P<redirect>.+)/$', ObtainApiAuthToken.as_view(), name='spark-login-handler'),
    url(r'^/me/$', CurrentUser.as_view(), name='me'),

    # Verify adult
    url(r'^/me/verify-adult/$', VerifyAdulthood.as_view(), name='verify-adult'),
    url(r'^/me/verify-adult/(?P<hash>.+)/$', VerifyAdulthood.as_view(), name='verify-adult-2nd-stage'),

    # Children, Students, Users:
    url(r'^/me/children/$', CurrentUserChildrenList.as_view(), name='my-children'),
    url(r'^/me/children/(?P<child_pk>\d+)/$', CurrentUserChildrenDetails.as_view(), name='my-children-detail'),
    url(r'^/me/children/(?P<child_pk>\d+)/password_reset/$', ResetOxygenPassword.as_view(), name='my-children-password-reset'),
    url(r'^/me/students/$', CurrentUserStudentsList.as_view(), name='my-students'),
    url(r'^/me/students/(?P<student_pk>\d+)/$', CurrentUserStudentsDetail.as_view(), name='my-students-detail'),
    url(r'^/me/users/$', CurrentUserUsersList.as_view(), name='my-users'),
    url(r'^/me/users/(?P<user_pk>\d+)/$', CurrentUserUsersDetail.as_view(), name='my-users-detail'),

    # Delegates:
    url(r'^/me/delegates/$', CurrentUserDelegateList.as_view(), name='my-delegates'),
    url(r'^/me/delegates/(?P<delegate_pk>\d+)/$', CurrentUserDelegateDetail.as_view(), name='my-delegates-detail'),
    url(r'^/me/delegators/$', CurrentUserDelegatorList.as_view(), name='my-delegators'),
    url(r'^/me/delegators/(?P<delegator_pk>\d+)/$', CurrentUserDelegatorDetail.as_view(), name='my-delegators-detail'),
    # Delegate Invites:
    url(r'^/me/delegates/invites/$', InviterDelegateInviteList.as_view(), name='owner-delegateinvite-list'),

    # Notifications:
    url(r'^/me/notifications/$', NotificationsList.as_view(), name='my-notifications'),
    url(r'^/me/notifications/(?P<pk>\d+)/mark_read/$', UnreadNotificationsDetail.as_view(), name='my-unread-single-notification'),
    url(r'^/me/notifications/(?P<pk>\d+)/mark_unread/$', RereadNotificationsDetail.as_view(), name='my-reread-single-notification'),
    url(r'^/me/notifications/unread/$', UnreadNotificationsList.as_view(), name='my-unread-notifications'),
    url(r'^/me/notifications/read/$', ReadNotificationsList.as_view(), name='my-read-notifications'),
)

user_urls = patterns('',
    url(r'^/$', UserList.as_view(), name='user-list'),
    url(r'^/(?P<pk>\d+)/$', UserDetail.as_view(), name='user-detail'),

    # User -> Activity
    url(r'^/(?P<user_pk>\d+)/state/classrooms/$', UserClassroomStateList.as_view(), name='user-classroom-state-list'),
    url(r'^/(?P<user_pk>\d+)/state/classrooms/(?P<classroom_pk>\d+)/$', UserClassroomStateDetail.as_view(), name='user-classroom-state-detail'),
    url(r'^/(?P<user_pk>\d+)/state/classrooms/(?P<classroom_pk>\d+)/projects/$', UserClassroomProjectStateList.as_view(), name='user-classroom-project-state-list'),
    url(r'^/(?P<user_pk>\d+)/state/classrooms/(?P<classroom_pk>\d+)/projects/(?P<project_pk>\d+)/$', UserClassroomProjectStateDetail.as_view(), name='user-classroom-project-state-detail'),
    url(r'^/(?P<user_pk>\d+)/state/projects/$', UserProjectStateList.as_view(), name='user-project-state-list'),
    url(r'^/(?P<user_pk>\d+)/state/projects/(?P<project_pk>\d+)/$', UserProjectStateDetail.as_view(), name='user-project-state-detail'),
    url(r'^/(?P<user_pk>\d+)/state/projects/(?P<project_pk>\d+)/lessons/$', UserProjectLessonStateList.as_view(), name='user-project-lesson-state-list'),
    url(r'^/(?P<user_pk>\d+)/state/projects/(?P<project_pk>\d+)/lessons/(?P<lesson_pk>\d+)/$', UserProjectLessonStateDetail.as_view(), name='user-project-lesson-state-detail'),

    # User -> Review
    url(r'^/(?P<user_pk>\d+)/reviews/$', UserReviewList.as_view(), name='user-review-list'),
    url(r'^/(?P<user_pk>\d+)/reviews/(?P<pk>\d+)/$', UserReviewDetail.as_view(), name='user-review-detail'),
)

invites_urls = patterns('',
    url(r'^/delegate/(?P<hash>[\w_\-]+)/$', InviteeDelegateInviteDetail.as_view(), name='self-delegateinvite-detail'),
)

