from django.contrib.auth import get_user_model
from django.http import response
from django.shortcuts import get_object_or_404
from django.db.models import Q
from notifications.models import Notification

from rest_framework import permissions, exceptions
from rest_framework.request import clone_request

from api.auth.models import ChildGuardian

from ..models import (
    Classroom,
    Project,
    Lesson,
    Step,
    ClassroomState,
    ProjectState,
    LessonState,
    StepState,
    ViewInvite,
    Review,
)


class ProjectAndLessonPermissionMixin(object):
    """
    Permission mixin to check user has permission for project and lesson.
    """
    _app_user_allowed_methods = ('PUT', 'PATCH', )
    _app_user_allowed_edit_models = (Lesson, Step, )
    _root_can_preview_permission_models = (Project, Lesson, Review, )

    def _project_edit_lock_permitted(self, request, view, root_project):
        try:
            force_edit_from_id = int(request.QUERY_PARAMS.get('forceEditFrom'))
        except (ValueError, TypeError):
            force_edit_from_id = None
        if root_project.is_user_edit_locked(request.user, force_edit_from_id=force_edit_from_id):
            raise exceptions.PermissionDenied('This project is currently being edited by another collaborator.')
        return True

    def _check_permission_on_root_project_and_lesson(self, request, view, root_project, root_lesson, check_read_only=False):
        if not root_project:
            raise exceptions.NotFound

        # Check that root_lesson is in root_project:
        if root_lesson:
            if root_lesson.project != root_project:
                raise exceptions.NotFound

        user = request.user

        if request.method in permissions.SAFE_METHODS or check_read_only:
            # Allow anything to super user:
            if user.is_superuser:
                return True

            # Allow read if user can at least preview:
            req_hash = request.QUERY_PARAMS.get('hash', None)
            root_project_read_permission_callback = root_project.can_preview if view.model in self._root_can_preview_permission_models else root_project.can_view
            if root_project_read_permission_callback(user, view_hash=req_hash):
                return True

            return False

        else:
            # Authenticated user:
            if user.is_authenticated():

                # Allow anything to super user:
                if user.is_superuser:
                    return self._project_edit_lock_permitted(request, view, root_project)

                # If got EDIT permission then allow (even adding):
                if (
                    root_project.can_edit(request.user)
                    or (
                        # For Project model allow also permissions for reedit, publish or editor when project in review/ready mode:
                        view.model == Project and (
                            root_project.can_reedit(request.user)
                            or root_project.can_publish(request.user)
                            or (root_project.publish_mode in [Project.PUBLISH_MODE_REVIEW, Project.PUBLISH_MODE_READY] and root_project.is_editor(request.user))  # editor can change minPublishDate
                        )
                    )
                ):
                    return self._project_edit_lock_permitted(request, view, root_project)

                # Application Permitted User (allowed only to edit application lessons).
                if request.method in self._app_user_allowed_methods and view.model in self._app_user_allowed_edit_models:
                    # If project is in state mode that can be edited (see conditions in .can_edit):
                    if (
                        root_project.publish_mode == Project.PUBLISH_MODE_EDIT
                    ):
                        user_app_groups = user.get_cache_application_groups()
                        # If root_lesson is set, then check the user is part of the lesson application group:
                        if root_lesson:
                            if root_lesson.application in user_app_groups:
                                return self._project_edit_lock_permitted(request, view, root_project)
                        # If root_lesson is not set, but user is part of any application group, then pass the .has_permission() method:
                        elif user_app_groups:
                            return self._project_edit_lock_permitted(request, view, root_project)

            return False


class ProjectAndLessonPermission(ProjectAndLessonPermissionMixin, permissions.BasePermission):
    """
    Checks user has permission for project and lesson.
    Also used to permit actions of deeper models (e.g steps, states, etc).

    IMPORTANT:
    Make sure to keep the common url kwargs in all urls using this mixin.
    Make sure to keep using the same _cache_root_* names to get objects without accessing database.
    """
    read_only = False

    def has_permission(self, request, view):
        #if view is under project_pk (but view model is actually not Project):
        if 'project_pk' in view.kwargs:
            root_project = view.get_cache_root_object(Project, 'pk', 'project_pk')

            #if view is under lesson_pk (but view model is actually not Lesson):
            root_lesson = None
            if 'lesson_pk' in view.kwargs:
                root_lesson = view.get_cache_root_object(Lesson, 'pk', 'lesson_pk')

            #check read permission for the root_project and root_lesson:
            if not self._check_permission_on_root_project_and_lesson(request, view, root_project, root_lesson, check_read_only=True):
                #if user can not view but can preview, then do not return NotFound but do not allow (return False - will raise 401 or 403):
                if view.model not in self._root_can_preview_permission_models and root_project.can_preview(request.user):
                    return False
                raise exceptions.NotFound

            #if request method is not for read only, then check the permission again for the request method:
            if request.method not in permissions.SAFE_METHODS and not self.read_only:
                if not self._check_permission_on_root_project_and_lesson(request, view, root_project, root_lesson, check_read_only=False):
                    return False

        return True

    def has_object_permission(self, request, view, obj):
        """Permission is based on the project .check_permission_PERM() method."""

        # Get root project object:
        root_project = None
        root_lesson = None
        if isinstance(obj, Project):
            root_project = obj
        elif isinstance(obj, Lesson):
            root_lesson = obj
            root_project = obj.project
        elif isinstance(obj, Step):
            root_lesson = obj.lesson
            root_project = obj.lesson.project
        elif isinstance(obj, Review):
            root_lesson = None
            root_project = None
            if isinstance(obj.content_object, Lesson):
                root_lesson = obj.content_object
                root_project = obj.content_object.project
            elif isinstance(obj.content_object, Project):
                root_lesson = None
                root_project = obj.content_object
            else:
                raise AssertionError('ProgrammingError: \'%s\' is not suitable for %s model of %s.' %(self.__class__.__name__, obj._meta.object_name, obj.content_object._meta.object_name))
        else:
            raise AssertionError('ProgrammingError: \'%s\' is not suitable for %s model.' %(self.__class__.__name__, obj._meta.object_name))

        # If view kwargs contain 'project_pk', then check that root_project PK is matching (same goes for lesson_pk):
        project_pk = view.kwargs.get('project_pk')
        if project_pk is not None:
            if not root_project or root_project.pk != int(project_pk):
                raise exceptions.NotFound
        lesson_pk = view.kwargs.get('lesson_pk')
        if lesson_pk is not None:
            if not root_lesson or root_lesson.pk != int(lesson_pk):
                raise exceptions.NotFound

        #check permission for the root_project and root_lesson (in case it was not already checked in .has_permission()):
        if (root_project and project_pk is None) or (root_lesson and lesson_pk is None):
            if not self._check_permission_on_root_project_and_lesson(request, view, root_project, root_lesson, check_read_only=self.read_only):
                return False

        return True

class ProjectAndLessonReadOnlyPermission(ProjectAndLessonPermission):
    read_only = True

    def has_object_permission(self, request, view, obj):
        #extend supported objects for the permission, for states:
        root_obj = obj
        if (
            isinstance(obj, ProjectState) or
            isinstance(obj, LessonState) or
            isinstance(obj, StepState)
        ):
            root_obj = getattr(obj, obj.get_state_subject(), None)

        # Check read-only permission on project and lesson:
        return super(ProjectAndLessonReadOnlyPermission, self).has_object_permission(request, view, root_obj)

class ProjectAndLessonWriteOnlyPermission(ProjectAndLessonPermission):
    def has_object_permission(self, request, view, obj):
        return super(ProjectAndLessonWriteOnlyPermission, self).has_object_permission(clone_request(request, 'PUT'), view, obj)
    def has_permission(self, request, view):
        return super(ProjectAndLessonWriteOnlyPermission, self).has_permission(clone_request(request, 'PUT'), view)


class ProjectAndLessonDraftPermission(ProjectAndLessonPermissionMixin, permissions.BasePermission):
    read_only = False

    def has_permission(self, request, view):
        #if view is under project_pk (but view model is actually not Project):
        if 'project_pk' in view.kwargs:
            root_project = view.get_cache_root_object(Project, 'pk', 'project_pk')  # origin root_project

            #if view is under lesson_pk (but view model is actually not Lesson):
            root_lesson = None
            if 'lesson_pk' in view.kwargs:
                root_lesson = view.get_cache_root_object(Lesson, 'pk', 'lesson_pk')  # origin root_lesson

            #check read permission for the origin root_project and root_lesson:
            if not self._check_permission_on_root_project_and_lesson(request, view, root_project, root_lesson, check_read_only=True):
                raise exceptions.NotFound

            # If for draft, then check that origin_root_project is in published mode:
            if root_project.publish_mode != Project.PUBLISH_MODE_PUBLISHED:
                raise exceptions.NotFound('Only published projects may use drafts.')

            # If root project has no draft:
            if not root_project.has_draft:
                # If view is draft list:
                if getattr(view, 'view_draft_list', False):
                    raise exceptions.NotFound

                # If user can create new draft for the project:
                if root_project.can_create_draft(request.user):
                    # If request method is allowed to create draft:
                    if request.method in ['PATCH', 'PUT']:
                        return True
                    # Otherwise, if request method depends on existing draft object:
                    raise exceptions.NotFound
                # Not allowed:
                return False

            # Get drafts of project and lesson:
            draft_root_project = root_project.draft_get()
            draft_root_lesson = root_lesson.draft_get() if root_lesson else None

            #check read permission for the draft root_project and root_lesson:
            if not self._check_permission_on_root_project_and_lesson(request, view, draft_root_project, draft_root_lesson, check_read_only=False):
                return False

        return True


class IsNotChild(permissions.BasePermission):
    '''
    Checks that the user is authenticated and is not a child.
    '''

    def has_permission(self, request, view):

        return (
            request.user and
            request.user.is_authenticated() and
            not request.user.is_child
        )


class IsNotChildOrReadOnly(permissions.BasePermission):
    '''
    User is an adult, or read only access if user is a child.
    '''
    def has_permission(self, request, view):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True

        return (
            request.user and
            request.user.is_authenticated() and
            not request.user.is_child
        )


class LessonProjectOwnerOrReadOnly(permissions.BasePermission):
    """
    Tests whether the object's lesson owner is the current user or not.

    Only the lesson owner can edit the object.
    """

    def has_permission(self, request, view):

        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS or request.user.is_superuser:
            return True

        # Get the owner of the root project:
        root_project = view.get_cache_root_object(Project, 'pk', 'project_pk')
        owner = root_project.owner
        user = request.user

        return (
            (not user.is_anonymous()) and 
            (owner ==  user or owner in user.children.all())
        )


class ClassroomPermission(permissions.IsAuthenticated):
    '''
    User is authenticated.
    User is owner, or read only access if user is student (or guardian of a student).
    '''
    read_only = False

    def has_object_permission(self, request, view, obj):
        if not super(ClassroomPermission, self).has_object_permission(request, view, obj):
            return False

        if 'classroom_pk' in view.kwargs:
            obj = root_classroom = view.get_cache_root_object(Classroom, 'pk', 'classroom_pk')

        #if owner:
        if obj.owner == request.user or request.user.is_superuser:
            #allow everything:
            return True
        #if not owner, and safe method:
        elif request.method in permissions.SAFE_METHODS or self.read_only:
            #allow approved student or guardian of approved student:
            return (
                obj.registrations.filter(
                    Q(status=ClassroomState.APPROVED_STATUS),  #approved
                    Q(user=request.user) | Q(user__in=request.user.childguardian_child_set.values('child'))  #student | guardian (child student)
                ).exists()
            )
        return False

    def has_permission(self, request, view):
        if not super(ClassroomPermission, self).has_permission(request, view):
            return False
        if 'classroom_pk' in view.kwargs:
            return self.has_object_permission(request, view, None)
        return True

class ClassroomReadOnlyPermission(ClassroomPermission):
    read_only = True

class ClassroomWriteOnlyPermission(ClassroomPermission):
    def has_permission(self, request, view):
        return super(ClassroomWriteOnlyPermission, self).has_permission(clone_request(request, 'PUT'), view)
    def has_object_permission(self, request, view, obj):
        return super(ClassroomWriteOnlyPermission, self).has_object_permission(clone_request(request, 'PUT'), view, obj)


class IsGuardianOrClassroomTeacher(permissions.BasePermission):
    '''
    Only allow the student herself (or her guardian), or her classroom teacher
    to view this.
    '''

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        # from rest_framework.generics import get_object_or_404
        # classroom = get_object_or_404(Classroom.objects.filter(pk=view.kwargs.get('classroom_pk')))

        if request.user.is_authenticated():
            if request.user.is_superuser:
                return True

            return get_user_model().objects.filter(
                Q(pk__in=ClassroomState.objects.filter(classroom__owner=request.user).values('user')) |  #students of the teacher (of any status)
                Q(pk__in=ChildGuardian.objects.filter(guardian=request.user).values('child'))  #children of the teacher
            ).filter(pk=view.kwargs['pk']).exists()

        return False


class IsSelfOrClassroomTeacher(permissions.IsAuthenticated):
    '''
    Only allow the student herself (or her guardian), or her classroom teacher
    to view this. Based on state object.
    '''

    def has_object_permission(self, request, view, obj):
        if not super(IsSelfOrClassroomTeacher, self).has_object_permission(request, view, obj):
            return False

        # Instance must be the logged in user or her child.
        return (
            obj.user == request.user or  #owner
            obj.classroom.owner == request.user or  #classroom teacher
            obj.user.get_cache_childguardian_guardian(request.user)  #guardian
        )


class SelfOrTeacherReadOnly(permissions.IsAuthenticated):
    '''
    Only allow the student herself (or her guardian), or her classroom teacher
    to view this. Based on user object.
    '''
    def has_object_permission(self, request, view, obj):
        if not super(SelfOrTeacherReadOnly, self).has_object_permission(request, view, obj):
            return False

        # Instance must be the logged in user or her child.
        if (
            request.user.is_superuser  #super user
            or obj == request.user  #self
            or obj.get_cache_childguardian_guardian(request.user)  #guardian
        ):
            return True
        # else if not self or guardian, but safe method:
        elif request.method in permissions.SAFE_METHODS:
            return (
                obj.classrooms_states.filter(classroom__in=request.user.authored_classrooms.all()).exists()  #classroom teacher
            )

class OnlySelf(permissions.IsAuthenticated):
    '''
    Only allow the guardian of a user or the user itself access.
    '''
    
    def has_object_permission(self, request, view, obj):

        # Instance must be the logged in user or her child.
        return (
            obj == request.user or  #self
            obj.get_cache_childguardian_guardian(request.user)  #guardian
        )


class SelfOrReadOnly(permissions.BasePermission):
    '''
    SAFE methods: Allowed to any user.
    UNSAFE: Only if the logged in user is the same as the object or her guardian. 
    '''
    
    def has_object_permission(self, request, view, obj):

        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:            
            return True

        # Instance must be the logged in user or her child.
        return (
            obj == request.user or
            obj.get_cache_childguardian_guardian(request.user)  #guardian
        )


class GuardianOrReadOnly(permissions.BasePermission):
    """
    SAFE methods: Allowed to any user.
    UNSAFE: Only if the logged in user is the guardian of the object.
    """

    def has_object_permission(self, request, view, obj):
        #SAFE methods are allowed to anyone:
        if request.method in permissions.SAFE_METHODS:
            return True

        #instance object must be child of the logged in user:
        return (
            obj.get_cache_childguardian_guardian(request.user)  #guardian
        )


class UsersExtraInfoPermission(permissions.IsAuthenticated):
    '''
    Only allow the student herself (or her guardian), or her classroom teacher
    to view this. Based on user object.
    '''
    def has_permission(self, request, view):
        if not super(UsersExtraInfoPermission, self).has_permission(request, view):
            return False

        user_obj = view.get_cache_root_object(get_user_model(), 'pk', 'user_pk')

        # User instance must be the logged in user or her child.
        if (
            request.user.is_superuser  #super user
            or user_obj == request.user  #self
            or user_obj.get_cache_childguardian_guardian(request.user)  #guardian
        ):
            return True
        # else if not self or guardian, but safe method:
        elif request.method in permissions.SAFE_METHODS:
            #queryset of classrooms states of the authored classrooms of the request user:
            classroom_states_qs = ClassroomState.objects.filter(view.get_allowed_q_filter_for_user(ClassroomState, user_obj))
            #if request user is not teacher of any classroom of the user, then deny access:
            if not classroom_states_qs.exists():
                return False
            #if classroom_pk then check that its classroom state exists:
            if 'classroom_pk' in view.kwargs:
                if not classroom_states_qs.filter(classroom=view.kwargs.get('classroom_pk')).exists():
                    raise exceptions.NotFound
            #if project_pk then check that its classroom state exists:
            if 'project_pk' in view.kwargs:
                if not classroom_states_qs.filter(classroom__projects=view.kwargs.get('project_pk')).exists():
                    raise exceptions.NotFound
            #when got to here then allow access:
            return True

        return False


class ProjectEditLock(ProjectAndLessonPermissionMixin, permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        #validate project is not edit locked:
        if request.method in view.allowed_methods and request.method not in permissions.SAFE_METHODS:
            return self._project_edit_lock_permitted(request, view, obj)

        return True


class ProjectDraftEditLock(ProjectEditLock):
    def has_object_permission(self, request, view, obj):
        # get the draft object:
        draft_obj = obj.draft_get()
        if not draft_obj:
            raise exceptions.NotFound

        return super(ProjectDraftEditLock, self).has_object_permission(request, view, draft_obj)


class ProjectModePermission(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if (
            obj.can_edit(request.user)
            or obj.can_reedit(request.user)
            or obj.can_publish(request.user)
            or (obj.publish_mode in [Project.PUBLISH_MODE_REVIEW, Project.PUBLISH_MODE_READY] and obj.is_editor(request.user))  # editor can change minPublishDate
        ):
            return True

        return False

class ProjectDraftModePermission(ProjectModePermission):
    def has_object_permission(self, request, view, obj):
        # get the draft object:
        draft_obj = obj.draft_get()
        if not draft_obj:
            raise exceptions.NotFound

        return super(ProjectDraftModePermission, self).has_object_permission(request, view, draft_obj)


class LessonCopyPermission(permissions.BasePermission):
    permission_denied_published_project = exceptions.PermissionDenied('Forbidden to update or delete projects not in edit mode.')

    def has_object_permission(self, request, view, obj):
        #super user allowed to edit project in any case:
        if request.user.is_superuser:
            return True

        #check object permission only if obj is Project:
        if isinstance(obj, Lesson):
            return obj.project.is_editor(request.user)

        #do not allow to update or delete published project:
        project_obj = obj if isinstance(obj, Project) else obj.project
        if not project_obj.can_edit(request.user):
            raise self.permission_denied_published_project

        return True


class IsReferredProjectOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        project = None
        if isinstance(obj, Project):
            project = obj
        elif isinstance(obj, ViewInvite):
            project = obj.project
        else:
            raise AssertionError('ProgrammingError: \'%s\' is suitable only for Project and ViewInvite models.' % (self.__class__.__name__,))

        return request.user == project.owner or project.owner.get_cache_ownerdelegate_delegate(request.user)


class ProjectLessonEditPermission(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        # superuser is allowed to edit projects and lessons
        if request.user.is_superuser:
            return True

        if request.method.upper() in view.allowed_methods and request.method not in permissions.SAFE_METHODS:
            #get root project for edit, and then use self.root_object_project_edit:
            view.get_root_object_project_edit()  #will throw exception if not permitted

            #if update, and user is part of an application group - then allow:
            if (
                obj and
                obj.id and
                request.method.upper() in ['PUT', 'PATCH'] and  #update methods
                request.user.is_authenticated() and
                obj.application in request.user.get_cache_application_groups()
            ):
                return True

            #otherwise - disallow:
            return False

        return True

    def has_permission(self, request, view):
        #for POST, check permission like for object:
        if request.method.upper() in ['POST']:
            return self.has_object_permission(request, view, None)
        return True


class ReviewEditByOwnerOrGuardianOnly(permissions.BasePermission):
    """
    SAFE methods: Allowed to any user.
    UNSAFE: Only if the logged in user is the guardian of the review owner.
    """

    def has_object_permission(self, request, view, obj):
        #SAFE methods are allowed to anyone:
        if request.method in permissions.SAFE_METHODS:
            return True

        # For unsafe methods allow only review owner or her guardian.
        owner = obj.owner
        user = request.user

        # owner:
        if obj.owner == request.user:
            return True

        # guardian:
        if owner.get_cache_childguardian_guardian(user):
            return True

        return False


class IsRecipient(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_authenticated() and request.user == obj.recipient:
            return True
        return False

    def has_permission(self, request, view):
        if request.user.is_authenticated():
            if request.method in permissions.SAFE_METHODS:
                return True
            return Notification.objects.filter(recipient=request.user).exists()
        return False
