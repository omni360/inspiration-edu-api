import urllib

from django.conf import settings
from django.core.cache import cache
from django.db.utils import IntegrityError
from django.shortcuts import redirect

from rest_framework.permissions import IsAuthenticated
from rest_framework.authtoken.models import Token
from rest_framework.authentication import TokenAuthentication
from rest_framework.response import Response
from rest_framework import status, exceptions
from rest_framework import generics, views
from api.models import Project, Lesson

from states.serializers import StepStateSerializer, LessonStartSerializer
from models import StepState, LessonState, ProjectState
from api.views.mixins import CacheRootObjectMixin
from api.views.permissions import ProjectAndLessonReadOnlyPermission


# region Step State
class StepStateCreate(views.APIView):
    permission_classes = (IsAuthenticated, )

    def post(self, request, *args, **kwargs):
        # Try to get lesson state that correspond with this step state (lesson state id cache is stored in LessonStart view)
        lesson_id = int(self.kwargs.get('lesson_pk'))
        lesson_state_id = cache.get('state_lesson_%d_user_%d' % (lesson_id, self.request.user.id))
        # If not found in cache - add find in DB and add to cache
        if not lesson_state_id:
            try:
                lesson_state_id = LessonState.objects.get(lesson_id=lesson_id, project_state__user_id=self.request.user.id).id
                # In case lesson state id was not in cache - put it there
                cache.set('state_lesson_%d_user_%d' % (lesson_id, self.request.user.id), lesson_state_id, timeout=60 * 45)
            except LessonState.DoesNotExist:
                return Response({'error': 'The lesson was not started properly'}, status=status.HTTP_412_PRECONDITION_FAILED)

        step_state_data = {
            'step_id': request.data['step'],
            'lesson_state_id': lesson_state_id,
            'user': self.request.user,
        }
        try:
            StepState.objects.create(**step_state_data)
        except IntegrityError:
            return Response({'error': 'This step is already marked as completed'}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_201_CREATED)


class StepStateDelete(generics.DestroyAPIView):
    permission_classes = (IsAuthenticated, )
    lookup_field = 'step__order'
    lookup_url_kwarg = 'order'

    def get_queryset(self):
        lesson_id = int(self.kwargs.get('lesson_pk'))
        # filter queryset by lesson id and user
        return StepState.objects.filter(lesson_state__lesson_id=lesson_id,
                                        user=self.request.user)
# endregion Step State


# region Lesson State
class QueryParamTokenAuthentication(TokenAuthentication):
    """
    TokenAuthentication extend, that gets token either from Authorization header or apiToken query-param.
    If redirect, then get token from apiToken query-param only.
    If no-redirect, then get token from Authorization header Token only.

    Note: Since the backend api uses AuthTokenFromCookie for admin (GET request), if user was logged in backend admin,
          the login cookie was used first for Authorization header Token. Therefore, for this URL we ignore the
          Authorization header (that might be feed from AUTH_TOKEN cookie) and force authentication only from the
          apiToken query-param.
    """
    def authenticate(self, request):
        # Default - not authenticated:
        user_auth_tuple = None

        # If redirect apiToken exists in query params, then use it for authentication:
        if request.query_params.get('no-redirect', 'false').lower() in ['0', 'false']:
            query_param_api_token = request.query_params.get('apiToken', None)
            if query_param_api_token:
                user_auth_tuple = self.authenticate_credentials(query_param_api_token)
        # Otherwise, if no-redirect=true, then use Authorization header for authentication:
        else:
            user_auth_tuple = super(QueryParamTokenAuthentication, self).authenticate(request)

        return user_auth_tuple


class LessonStart(CacheRootObjectMixin, generics.GenericAPIView):
    model = LessonState
    serializer_class = LessonStartSerializer
    authentication_classes = (QueryParamTokenAuthentication,)
    permission_classes = (ProjectAndLessonReadOnlyPermission,)

    def get(self, request, *args, **kwargs):
        # Get project and lesson
        project = self.get_cache_root_object(Project, 'pk', 'project_pk')
        lesson = self.get_cache_root_object(Lesson, 'pk', 'lesson_pk')

        # Create project and lesson states if does not exist
        project_state, _ = ProjectState.objects.get_or_create(project=project, user=request.user)
        lesson_state, lesson_state_created = LessonState.objects.get_or_create(project_state=project_state, lesson=lesson, defaults={'user': request.user})

        # Store the lesson state id in cache for lesson duration:
        cache.set('state_lesson_%d_user_%d' % (lesson.id, self.request.user.id), lesson_state.id, timeout=60 * 45)

        # If lesson belongs to tinkercad or circuits build a redirect link
        query_params = self.request.query_params
        if query_params.get('no-redirect', 'false').lower() in ['0', 'false']:
            lesson_app_key = settings.LESSON_APPS_KEY_FROM_DB_NAME.get(lesson.application)

            # Form a redirect link
            to_link = settings.LESSON_APPS[lesson_app_key].get('lesson_url', settings.IGNITE_LESSON_START_URL)

            # Tinkercad, Circuits:
            if lesson.application in ['tinkercad', '123dcircuits']:
                # Make link query params
                params = {
                    key: val for key, val in query_params.items() if key != 'apiToken'
                }
                params.update({
                    'edu-project-id': project.id,
                    'edu-lesson-id': lesson.id
                })
                if lesson.application == 'tinkercad':
                    lesson_state.get_canvas_external_params(update_params=params)
                elif lesson.application == '123dcircuits':
                    document_id, is_init = lesson_state.get_canvas_document_id()
                    if not is_init:
                        to_link = settings.LESSON_APPS[lesson_app_key]['lesson_with_id_url']
                        params.update({
                            'edu-circuit-id': document_id,
                            'edu-member-id': request.user.member_id
                        })
                to_link += '?' + urllib.urlencode(params)
            # Lagoa (not implemented):
            elif lesson.application == 'lagoa':
                return Response(data={'detail': 'Not Implemented'}, status=status.HTTP_501_NOT_IMPLEMENTED)
            # Video, Step by step, Instructables -> redirects to frontend:
            else:
                to_link += 'project/%d/lesson/%d/' % (project.id, lesson.id)

            # Returns redirect
            return redirect(to_link, permanent=False, *args, **kwargs)

        # Return Lesson Related Data
        serializer = self.get_serializer(instance=lesson_state)
        return Response(serializer.data, status=status.HTTP_201_CREATED if lesson_state_created else status.HTTP_200_OK)
# endregion Lesson State
