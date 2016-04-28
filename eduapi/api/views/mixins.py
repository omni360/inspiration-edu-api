import types
from django.db.models import Q
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404
from django.http import Http404
from rest_framework import generics
from rest_framework import exceptions
from rest_framework.request import clone_request
from rest_framework.filters import OrderingFilter

from .filters import MappedOrderingFilter
from ..models import Classroom, Project, Lesson, Step, Review, ClassroomState, ProjectState, LessonState, StepState, IgniteUser, Purchase


class RootViewBuilder(object):
    '''
    This root view builder is helper class to create nested views.
    It helps to define the view queryset based on the root view object.

    Simply inherit this builder to your nested view class, and define the root view:

        root_view_name              - the default name of the root view object.
        root_view_class             - the root view class (must be subclass of generics.GenericAPIView).
        root_view_options           - default options for the root view (default: {'request_method': 'GET'}).
        root_view_use_object        - flag whether to use the root object or queryset (default: True).
        root_view_lookup_url_kwarg  - the lookup url kwarg to get the root view pk.
                                      available only when root_view_use_object is True.
        root_view_objects           - list of predefined root objects, of the form: {'rootobj_edit': {'request_method': 'PUT', ...}, ...}
                                      a default root_view_object will always be created with root_view_name and root_view_options.
                                      available only when root_view_use_object is True.
                                      By default, when accessing the root_object, all prefetch_related is emptied (for optimization).
                                      If prefetch is needed, use 'with_prefetch' True.

        def make_root_queryset(self, root_object):
            #root_object argument is the default root object from the root view (root_view_objects[root_view_name]).
            root_qs = root_object.<field>.all()
            #... you can alter the root queryset more as you wish ...#
            return root_qs

    IMPORTANT:
    In order to have the magic work, you must define all your root view settings attributes TOGETHER in single class!
    [The builder reads the attributes from each root class separately and all together, avoiding inheritance].

    After initializing, then in the view you can have these methods:

        get_root_queryset(self, root_queryset=None, until_class=None)
            Returns the root queryset.
            Mainly used to initialize self.queryset for get_queryset.
            This will throw exception if cannot get the root queryset.

        get_root_object_<root_view_object_key>(self) -> self.root_object_<root_view_object_key>
            Returns the root object with the given key as defined in root_view_objects.
            Mainly used to get (with permission check) the root object for view actions methods.
            This will throw exception if cannot get the root object.
    '''

    def _prepare_view(self, view_class, lookup_url_kwarg, request_method='GET', queryset=None,
                                  action_request=None, action_args=None, action_kwargs=None,
                                  permission_classes=None, authentication_classes=None, override_options=None):
        '''
        Prepares the root view for action.
        '''

        #defaults:
        action_request = action_request if action_request is not None else self.request
        action_args = action_args if action_args is not None else self.args
        action_kwargs = action_kwargs if action_kwargs is not None else self.kwargs

        #make the view instance:
        view_instance = view_class(lookup_url_kwarg=lookup_url_kwarg)
        view_instance.args = action_args
        view_instance.kwargs = action_kwargs
        view_instance.request = clone_request(action_request, request_method)  #clone the same request but with GET method

        #IMPORTANT: set the queryset of the root view to the current queryset:
        #(this allows to concatenate RootViewBuilder's)
        view_instance.queryset = queryset

        #Do not override permission/authentication classes, but add to them to strict more:
        #The rationale beyond this is that any inner object in the url is not accessible if the
        #former object in the URL is not accessible.
        if permission_classes is not None:
            view_instance.permission_classes += permission_classes
        if authentication_classes is not None:
            view_instance.authentication_classes += authentication_classes

        #override more options (preferred not to use it):
        if isinstance(override_options, dict):
            for opt_key, opt_val in override_options:
                if hasattr(view_instance, opt_key):
                    setattr(view_instance, opt_key, opt_val)

        #initialize the view instance:
        view_instance.initial(view_instance.request, *action_args, **action_kwargs)

        return view_instance

    def get_root_object_from_view(self, *args, **kwargs):
        '''
        Gets object from another view (root_view_use_object = True).
        Just set which request method to use (defaults to 'GET'), and the lookup_url_kwarg parameter.
        '''
        with_prefetch = kwargs.pop('with_prefetch', None)
        view_instance = kwargs.pop('view_instance', None)
        view_instance = view_instance or self._prepare_view(*args, **kwargs)
        queryset = self.get_root_queryset_from_view(view_instance=view_instance, with_prefetch=with_prefetch)
        return view_instance.get_object()

    def get_root_queryset_from_view(self, *args, **kwargs):
        '''
        Gets queryset from another view (root_view_use_object = False).
        Just set which request method to use (defaults to 'GET').
        '''
        with_prefetch = kwargs.pop('with_prefetch', None)
        with_prefetch = with_prefetch if with_prefetch is not None else False
        view_instance = kwargs.pop('view_instance', None)
        view_instance = view_instance or self._prepare_view(*args, **kwargs)
        queryset = view_instance.get_queryset()
        if not with_prefetch:
            queryset = queryset.prefetch_related(None)
        return queryset

    def get_root_object_or_queryset_from_view(self, root_view_use_object, *args, **kwargs):
        '''
        Gets queryset or object from another view (based on root_view_use_object).
        '''
        if root_view_use_object:
            return self.get_root_object_from_view(*args, **kwargs)
        return self.get_root_queryset_from_view(*args, **kwargs)

    def check_root_object_permissions_from_view(self, *args, **kwargs):
        '''
        Checks object permission from another view.
        Just set the lookup_url_kwarg parameter, and which request method to use (defaults to 'GET').
        You can restrict more permissions and authentications with permission_classes and authentication_classes.
        '''
        view_instance = self._prepare_view(*args, **kwargs)
        return view_instance.check_permissions(view_instance.request)

    @classmethod
    def make_get_root_object_method(cls, root_class, attr_name, *args, **kwargs):
        '''
        Adds get_root_object_<attr_name>() method to the class of self.
        That method gets the root object, and stores it in self.root_object_<attr_name>.
        *args and **kwargs are transferred to get_root_object_from_view() method.
        '''
        self_attr_name = 'root_object_' + attr_name
        def get_root_object_method(self):
            if not hasattr(self, self_attr_name):
                kwargs['queryset'] = self.get_root_queryset(until_class=root_class)
                setattr(self, self_attr_name, self.get_root_object_from_view(*args, **kwargs))
            return getattr(self, self_attr_name)
        setattr(cls, 'get_' + self_attr_name, get_root_object_method)

    @classmethod
    def make_get_root_queryset(cls, root_view_use_object, root_class, root_view_class, root_view_lookup_url_kwarg, root_view_options):
        def wrapper(func):
            def wrapped_get_root_queryset(self, root_queryset=None, until_class=None, of_class=None):
                #if we have already got to until_class, then return the passed root_queryset:
                if ((until_class and (not issubclass(until_class, root_class) or until_class is root_class)) or
                    (of_class and not issubclass(of_class, root_class))):
                    return root_queryset

                #get the root object or queryset with the default root_view_options:
                root_view_options['queryset'] = root_queryset  #set root queryset
                root_obj_or_qs = self.get_root_object_or_queryset_from_view(root_view_use_object, root_view_class, root_view_lookup_url_kwarg, **root_view_options)
                #alter the root queryset by passing the root object or queryset to func:
                root_queryset = func(self, root_obj_or_qs)

                #if we have already got to of_class, then return the current root_queryset:
                if of_class and of_class is root_class:
                    return root_queryset

                #continue to build the root queryset from this root class:
                return super(root_class, self).get_root_queryset(root_queryset, until_class, of_class)
            return wrapped_get_root_queryset
        return wrapper

    def __new__(cls, *args, **kwargs):
        '''
        This is called before instantiating a class object, to build the root view methods and behavior.
        '''

        #if class was not yet initialized with RootViewBuilder, then initialize class:
        if not getattr(cls, '__root_view_initialized__', False):

            #go over the classes that inherit RootViewBuilder and build them:
            for base_class in cls.mro():
                #if got to self base_class, then stop:
                if base_class is RootViewBuilder:
                    break

                #access only attributes defined on the class (because getting attribute with base_class access also inherited attributes):
                base_class_dict = base_class.__dict__

                #get class settings:
                root_view_name = base_class_dict.get('root_view_name', None)
                root_view_class = base_class_dict.get('root_view_class', None)
                root_view_options = base_class_dict.get('root_view_options', {
                    'request_method': 'GET'
                })  #default root view options

                #got enough settings to make get_root_object methods:
                if root_view_name and root_view_class:
                    #get more class settings:
                    root_view_use_object = base_class_dict.get('root_view_use_object', True)  #whether to use object (default: True)
                    root_view_lookup_url_kwarg = base_class_dict.get('root_view_lookup_url_kwarg', None)  #lookup_url_kwarg attribute in case of using objects

                    #if root view use objects, then make get_root_object methods:
                    if root_view_use_object:
                        #get more class settings:
                        root_view_objects = base_class_dict.get('root_view_objects', {})

                        #make default get_root_object method:
                        root_view_objects[root_view_name] = root_view_options

                        #make get_root_object methods as in settings:
                        for root_view_obj_name, root_view_obj_kwargs in root_view_objects.iteritems():
                            cls.make_get_root_object_method(base_class, root_view_obj_name,
                                                            view_class=root_view_class, lookup_url_kwarg=root_view_lookup_url_kwarg,
                                                            **root_view_obj_kwargs)

                    #if got enough settings to make get_root_queryset method:
                    meth_get_root_queryset = base_class_dict.get('make_root_queryset', None)  #make_root_queryset base_class method
                    if meth_get_root_queryset:
                        #wrap the get_root_queryset method:
                        wrapped_meth_get_root_queryset = cls.make_get_root_queryset(root_view_use_object, base_class, root_view_class, root_view_lookup_url_kwarg, root_view_options)(meth_get_root_queryset)
                        # wrapped_meth_get_root_queryset.__name__
                        setattr(base_class, 'get_root_queryset', wrapped_meth_get_root_queryset)

            setattr(cls, '__root_view_initialized__', True)

        return super(RootViewBuilder, cls).__new__(cls, *args, **kwargs)

    def get_root_queryset(self, root_queryset=None, until_class=None, of_class=None):
        '''
        Returns the root view queryset.
        '''
        self.root_queryset = root_queryset
        return self.root_queryset

    def get_queryset(self):
        #set the initial queryset to root queryset (truncates attribute):
        self.queryset = getattr(self, 'root_queryset', self.get_root_queryset())
        return super(RootViewBuilder, self).get_queryset()


class DisableHttpMethodsMixin(object):
    '''
    Disables view methods.
    For http methods use attribute 'disable_http_methods'.
    For operation methods use attribute 'disable_operation_methods'.
    '''
    disable_http_methods = []
    disable_operation_methods = []

    def __init__(self, *args, **kwargs):
        super(DisableHttpMethodsMixin, self).__init__(*args, **kwargs)

        #map operation to http method name:
        map_operation_to_http = {
            'retrieve': 'get',
            'update': 'put',
            'partial_update': 'patch',
            'destroy': 'delete',
            'list': 'get',
            'create': 'post',
            'metadata': 'options',
        }

        #get list of http method names to disable from 'disable_http_methods' attribute:
        disable_http_method_names = [m.lower() for m in self.disable_http_methods]
        #get list of http method names to disable from 'disable_operation_methods' attribute:
        disable_http_method_names += [map_operation_to_http[o] for o in self.disable_operation_methods if map_operation_to_http.has_key(o)]

        #remove disabled http method names from http_method_names:
        self.http_method_names = [m for m in self.http_method_names if m not in disable_http_method_names]


class UpdateWithCreateMixin(object):
    '''
    This mixin makes the view having PUT-as-create behavior, and POST-as-update.
    The POST method is redirected to PUT .update() method.
    The method .perform_create() called by POST method is now out of use. Instead, .perform_update() method handles
    both updating and creating.
    Pay attention: .perform_update() might have serializer.instance None.
    '''
    #list of http methods that will be used for update with create:
    update_with_create_methods = ['POST', 'PUT']  #possible to add PATCH

    def get_object(self):
        try:
            obj = super(UpdateWithCreateMixin, self).get_object()
        except Http404:
            #For PUT-as-create, return None when object is not found:
            if self.request.method in self.update_with_create_methods:
                obj = None
            else:
                raise
        return obj

    def create(self, request, *args, **kwargs):
        '''
        Since using PUT-as-create, then redirect POST (create) to PUT (update), and handle both create and update in .perform_update.
        '''
        return self.update(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        '''
        Add POST method to view.
        '''
        return self.create(request, *args, **kwargs)


class BulkUpdateWithCreateMixin(object):
    '''
    Like UpdateWithCreateMixin, but for bulk create and bulk update:
    '''
    def create(self, request, *args, **kwargs):
        bulk = isinstance(request.data, list)

        #if not bulk, use regular create:
        if not bulk:
            return super(BulkUpdateWithCreateMixin, self).create(request, *args, **kwargs)

        #if bulk, use bulk create as bulk update:
        else:
            self.request = clone_request(request, 'PUT')
            return self.bulk_update(self.request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        '''
        Add POST method to view.
        '''
        return self.create(request, *args, **kwargs)


class UseAuthenticatedSerializerMixin(object):
    def get_serializer_class(self):
        if self.request.user.is_authenticated() and self.request.GET.get('user', '') == 'current':
            return self.authenticated_serializer_class
        return self.serializer_class


class EnrichSerializerContextMixin(object):
    embed_choices = tuple()
    embed_user_related = tuple()
    embed_list_base = []

    #Note: Theses are not class attributes, but instance attributes
    # embed_list = []
    # embed_user = None

    def initial(self, request, *args, **kwargs):
        #set embed list for the view, initialized from the query params plus base embed list:
        self.embed_list = self.embed_list_base[:]  #copy list
        embed = request.GET.get('embed', '')
        request_embed_list = set(embed.split(','))
        self.embed_list += [x for x in request_embed_list if x in self.embed_choices]

        #add user related fields:
        self.embed_user = None
        if self.request.user.is_authenticated() and self.request.GET.get('user', '') == 'current':
            self.embed_list += self.embed_user_related
            self.embed_user = self.request.user

        super(EnrichSerializerContextMixin, self).initial(request, *args, **kwargs)

    def get_serializer_context(self):
        context = super(EnrichSerializerContextMixin, self).get_serializer_context()
        context['allowed'] = tuple(self.embed_list)
        return context


class CacheRootObjectMixin(object):
    """
    Generic view mixin that defines a method to get and cache root object from the url kwargs.
    """
    def get_cache_root_object(self, model, lookup_field='pk', lookup_url_kwarg=None, queryset=None, cache_root_name=None, raise_not_found=True):
        """
        Gets the root object and caches it.

        :param model: The model class (used to fetch defaults for other parameters).
        :param lookup_field: The lookup field for getting the object (default 'pk').
        :param lookup_url_kwarg: Yhe lookup url kwarg for getting the value of the lookup field (default {model_name}_{lookup_field}).
        :param queryset: The queryset to get the object from (default model.objects.all()).
        :param cache_root_name: The name of the cache root object (default {model_name}) - sets cache in the view as attribute _cache_root_{cache_root_name}.
        :param raise_not_found: Whether to raise DRF exception NotFound if object is not found. If False then return None. (default True).
        :return: The object or None if not exists (if raise_not_found is True then raises DRF exception NotFound instead of returning None).
        """
        model_name = model._meta.model_name
        cache_root_name = cache_root_name or model_name
        cache_key = '_cache_root_' + cache_root_name
        cache_object = None
        if hasattr(self, cache_key):
            cache_object = getattr(self, cache_key)
        else:
            lookup_field = lookup_field or 'pk'
            lookup_url_kwarg = lookup_url_kwarg or '{}_{}'.format(model_name, lookup_field)
            lookup_value = self.kwargs.get(lookup_url_kwarg, None)
            if lookup_value is not None:
                queryset = queryset if queryset is not None else model.objects.all()
                #get cache object
                try:
                    cache_object = queryset.get(**{lookup_field: lookup_value})
                except model.DoesNotExist:
                    pass
            setattr(self, cache_key, cache_object)
        if cache_object is None and raise_not_found:
            raise exceptions.NotFound
        return cache_object


class FilterAllowedMixin(object):
    """
    This mixin is responsible to filter allowed objects.
    It is commonly used in views to filter allowed objects for deeper related objects,
    based on common url kwargs (e.g project_pk, lesson_pk, etc).

    IMPORTANT:
    Make sure to put all the Q filters of *allowed* objects of models in this mixin.
    Do not filter out disallowed objects in views querysets (put it in this mixin).
    Do not filter query-params in this mixin (e.g isArchived for /classrooms/ list).
    Make sure to keep the common url kwargs in all urls using this mixin.
    """

    def get_allowed_q_filter(self, model=None, **kwargs):
        # Default model:
        if model is None:
            model = self.model

        if model == Classroom:
            include_children_classrooms = kwargs.get('include_children_classrooms', True)
            exclude_archived_classrooms = kwargs.get('exclude_archived_classrooms', False)
            return self._get_allowed_q_filter_for_classroom(model, include_children_classrooms=include_children_classrooms, exclude_archived_classrooms=exclude_archived_classrooms)
        elif model in (Project, Lesson, Step, ProjectState, LessonState, StepState,):
            exclude_non_searchable_projects = kwargs.get('exclude_non_searchable_projects', False)
            return self._get_allowed_q_filter_for_project_lesson_step(model, exclude_non_searchable_projects=exclude_non_searchable_projects)
        elif model == Review:
            return self._get_allowed_q_filter_for_review(model)

        # If model not supported, then raise error:
        raise AssertionError('ProgrammingError: \'%s\' does not support \'%s\' model.' % (self.__class__.__name__, model.__name__))

    def _get_allowed_q_filter_for_project_lesson_step(self, model, exclude_non_searchable_projects=False):
        user = self.request.user

        # If super user, then do not filter (using empty Q):
        if user.is_superuser:
            return Q()

        # Get query fields lookups (acronym: qfl):
        qfl = None
        if model == Project:
            qfl = {
                'pk': 'pk',
                'publish_mode': 'publish_mode',
                'owner': 'owner',
                'application': None,
                'is_searchable': 'is_searchable',
                'hash': 'view_invite__hash',
            }
        elif model == Lesson:
            qfl = {
                'pk': 'project__pk',
                'publish_mode': 'project__publish_mode',
                'owner': 'project__owner',
                'application': 'application',
                'is_searchable': 'project__is_searchable',
                'hash': 'project__view_invite__hash',
            }
        elif model == Step:
            qfl = {
                'pk': 'lesson__project__pk',
                'publish_mode': 'lesson__project__publish_mode',
                'owner': 'lesson__project__owner',
                'application': 'lesson__application',
                'is_searchable': 'lesson__project__is_searchable',
                'hash': 'lesson__project__view_invite__hash',
            }
        elif model == ProjectState:
            qfl = {
                'pk': 'project__pk',
                'publish_mode': 'project__publish_mode',
                'owner': 'project__owner',
                'application': None,
                'is_searchable': 'project__is_searchable',
                'hash': 'project__view_invite__hash',
            }
        elif model == LessonState:
            qfl = {
                'pk': 'lesson__project__pk',
                'publish_mode': 'lesson__project__publish_mode',
                'owner': 'lesson__project__owner',
                'application': 'lesson__application',
                'is_searchable': 'lesson__project__is_searchable',
                'hash': 'lesson__project__view_invite__hash',
            }
        elif model == StepState:
            qfl = {
                'pk': 'step__lesson__project__pk',
                'publish_mode': 'step__lesson__project__publish_mode',
                'owner': 'step__lesson__project__owner',
                'application': 'step__lesson__application',
                'is_searchable': 'step__lesson__project__is_searchable',
                'hash': 'step__lesson__project__view_invite__hash',
            }

        # Filter by published content and searchable.
        published_filter = Q(**{qfl['publish_mode']: Project.PUBLISH_MODE_PUBLISHED})
        # Exclude non-searchable (hidden) projects.
        if exclude_non_searchable_projects:
            published_filter &= Q(**{qfl['is_searchable']: True})
        filters = published_filter

        # Filter by matching request 'hash' query param:
        req_hash = self.request.QUERY_PARAMS.get('hash', False)
        if req_hash:
            filters |= Q(**{qfl['hash']: req_hash})

        # If the user is logged in
        if user and not user.is_anonymous():

            # Or unpublished content that belongs to the user or her delegators/children.
            filters |= Q(**{qfl['owner']: user})
            filters |= Q(**{qfl['owner']+'__in': user.delegators.all()})
            filters |= Q(**{qfl['owner']+'__in': user.children.all()})

            #TODO: add OR filter for project/lessons in review/ready mode for reviewer users.
            # (currently reviewer=superuser, which are already handled above to get access to all).

            #IMPORTANT NOTE:
            #   Usually projects for purchase are searchable and published, therefore they are already included in the queryset.
            #   This handles an edge case when a project is_searchable=False (and publish_mode=published) and lock=True
            #   (not searchable and for purchase), and because it adds overhead to the query (more JOIN),
            #   therefore it is commented out.
            #TODO: Uncomment the following couple lines of code when it is required.
            # if exclude_non_searchable_projects:
            #     filters |= Q(**{qfl['publish_mode']: Project.PUBLISH_MODE_PUBLISHED, qfl['pk']+'__in': user.purchases.values('project')})

            # This is an ugly patch.
            # We want to let applications get the lessons that belong
            # to them and every project (because lessons belong to project
            # and projects don't have an application).
            # If you find a better solution for this, feel free to refactor.

            # Get a list of apps that this user is affiliated with.
            user_apps = Lesson.get_user_app_groups(user)
            if user_apps:
                # Projects - if user is affiliated with any app, show all project.
                if model == Project:
                    filters = Q()
                # Lessons or Steps - also allow.
                else:
                    filters |= Q(**{qfl['application']+'__in': user_apps})

        return filters

    def _get_allowed_q_filter_for_classroom(self, model, include_children_classrooms=True, exclude_archived_classrooms=False):
        user = self.request.user

        if user and not user.is_anonymous():
            # If super user, then do not filter (using empty Q):
            if user.is_superuser:
                return Q()

            # Filter owned classrooms.
            filters = Q(owner=user)

            # Filter registered classrooms:
            classroom_states_filter_q = Q(user=user)  #student
            if include_children_classrooms:
                classroom_states_filter_q |= Q(user__in=user.childguardian_child_set.values('child'))  #child student (user is guardian)
            classroom_states_qs = ClassroomState.objects.filter(
                Q(status=ClassroomState.APPROVED_STATUS),  #approved
                classroom_states_filter_q  #student user filter (user with/without children)
            )
            registered_classrooms_filter = Q(pk__in=classroom_states_qs.values('classroom'))
            if exclude_archived_classrooms:
                registered_classrooms_filter &= Q(is_archived=False)
            filters |= registered_classrooms_filter

            return filters
        else:
            # Not logged-in users have no access to any project:
            return Q(pk__isnull=True)  #will match nothing

    def _get_allowed_q_filter_for_review(self, model):
        filters = Q(content_type__model=Lesson._meta.model_name) & self.get_allowed_q_filter(Lesson)
        filters |= Q(content_type__model=Project._meta.model_name) & self.get_allowed_q_filter(Project)
        return filters

    def get_allowed_q_filter_for_user(self, model, user, **kwargs):
        # Default model:
        if model is None:
            model = self.model

        if model in (ClassroomState, ProjectState, LessonState,):
            return self._get_allowed_q_filter_for_users_states(model, user)
        elif model == Review:
            return self._get_allowed_q_filter_for_users_reviews(model, user)

        # If model not supported, then raise error:
        raise AssertionError('ProgrammingError: \'%s\' does not support \'%s\' model.' % (self.__class__.__name__, model.__name__))

    def __can_request_user_access_user(self, user):
        """Returns whether a request user can access the user info"""
        #try get it from self cache:
        request_user_access_users = getattr(self, '_cache_request_user_access_users', {})
        can_access = request_user_access_users.get(user.id, None)
        #if not in cache, then check if can access and cache in self:
        if can_access is None:
            if (
                self.request.user.is_superuser or  #request user is super user
                self.request.user == user or  #request user is the user itself
                user.get_cache_childguardian_guardian(self.request.user)  #request user is guardian of the user
            ):
                can_access = True
            else:
                can_access = False
            request_user_access_users[user.id] = can_access
            setattr(self, '_cache_request_user_access_users', request_user_access_users)
        return can_access

    def _get_allowed_q_filter_for_users_states(self, model, user):
        # Get query fields lookups (acronym: qfl):
        qfl = None
        if model == ClassroomState:
            qfl = {
                'user': 'user',
                'project': None,
                'classroom': 'classroom'
            }
        elif model == ProjectState:
            qfl = {
                'user': 'user',
                'project': 'project',
            }
        elif model == LessonState:
            qfl = {
                'user': 'project_state__user',  #TODO: When lesson state has its own 'user' field then use it
                'project': 'lesson__project',
            }
        state_subject = model.get_state_subject()

        # Filter states for the user:
        filters = Q(**{qfl['user']: user})

        # If request user is not allowed to access all states, then filter states of the authored classrooms only:
        if not self.__can_request_user_access_user(user):
            if state_subject == 'classroom':
                filters &= Q(**{'{}__owner'.format(qfl['classroom']): self.request.user})
            else:
                filters &= Q(**{
                    '{}__in'.format(qfl['project']): user.classrooms_states.filter(classroom__owner=self.request.user).values('classroom__projects')
                })

        return filters

    def _get_allowed_q_filter_for_users_reviews(self, model, user):
        filters = Q(owner=user)

        # If request user is not allowed to access all reviews, then filter reviews of the authored classrooms only:
        if not self.__can_request_user_access_user(user):
            user_classroom_states_qs = ClassroomState.objects.filter(self._get_allowed_q_filter_for_users_states(ClassroomState, user))
            filters &= (
                Q(  #teacher classroom - project reviews
                    content_type=ContentType.objects.get_for_model(Project),
                    object_id__in=user_classroom_states_qs.values('classroom__projects')
                )
            )

        return filters


class ChoicesOnGet(object):

    def metadata(self, request):

        ret = super(ChoicesOnGet, self).metadata(request)

        ret['actions'] = ret.get('actions', {})

        serializer = self.get_serializer()
        get_meta = serializer.metadata()

        ret['actions']['GET'] = {
            key: {u'choices': val['choices']}
            for key, val
            in get_meta.items()
            if val.get('choices')
        }

        return ret


class MappedOrderingView(generics.GenericAPIView):
    '''
    Adds MappedOrderingFilter to the filter_backends of the view.
    '''
    ordering_fields_map = {}

    def initial(self, request, *args, **kwargs):
        super(MappedOrderingView, self).initial(request, *args, **kwargs)

        #replace OrderingFilter with MappedOrderingFilter, or append MappedOrderingFilter:
        if MappedOrderingFilter not in self.filter_backends:
            if OrderingFilter in self.filter_backends:
                self.filter_backends = tuple([MappedOrderingFilter if fb==OrderingFilter else fb for fb in self.filter_backends])
            else:
                self.filter_backends += (MappedOrderingFilter,)


#DEPRECATED!
#NOTE: Since DRF 3 this mixin is not required anymore, because DRF 3 updates the instance before serializing, and
#      expects the programmer to update the instance as well - Serializer .update() and .create() methods.
class PrefetchViewMixin(object):
    '''
    Defines how to prefetch_related and select_related the view queryset, or add annotate/extra fields.
    Optionally handles re-prefetch of the object post saving (post_save_prefetch=False by default). Use this option
    when the view is able to change related objects.
    '''
    post_save_prefetch = False

    def __new__(cls, *args, **kwargs):
        instance = super(PrefetchViewMixin, cls).__new__(cls, *args, **kwargs)

        #get the original get_queryset method of the instance:
        get_queryset_method = getattr(instance, 'get_queryset')

        #define a new get_queryset method to preform prefetch after getting the queryset:
        def get_queryset_with_prefetch(self):
            #call original get_queryset method of the instance:
            queryset = get_queryset_method()

            #prefetch queryset:
            queryset = self.prefetch_queryset(queryset)

            return queryset

        #set the new get_queryset method:
        instance.get_queryset = types.MethodType(get_queryset_with_prefetch, instance, cls)

        return instance

    def prefetch_queryset(self, queryset):
        '''
        Gets a queryset and only adds prefetch_related and select_related to it, or add annotate/extra fields.
        Do not filter or exclude objects of the queryset in this method.
        '''
        return queryset

    def post_save(self, obj, created=False):
        super(PrefetchViewMixin, self).post_save(obj, created)

        #re-prefetch the object only in case the object is updated:
        if self.post_save_prefetch:
            #get the object again re-prefetched, and copy all attributes from the new object:
            #Note: The reason for copying all attributes is that the obj parameter given in this method is the object in
            #      serializer, and there's no way to replace that object in the serializer, so we update the current one.
            new_obj = self.prefetch_queryset(self.model.objects.all()).get(pk=obj.pk)
            obj.__dict__ = new_obj.__dict__.copy()
