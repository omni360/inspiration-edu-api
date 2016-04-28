import calendar
from datetime import datetime, timedelta
from django.conf import settings
from django.db.models import Min, Count, Q
from django.views.generic import TemplateView
from django.utils.timezone import now as utc_now

from api.auth.models import IgniteUser
from api.models import ProjectState, Project, Classroom, ChildGuardian

from guardian_moderation import _has_moderation_permission


def _helper_get_months_back_date_range(months_back=0):
    now = utc_now()
    # Get date at the beginning of the month
    gte_datetime = now - timedelta(days=now.day-1)
    # move back by the month
    for i in range(months_back):
        # Substruct one day to move to previous month
        gte_datetime = gte_datetime - timedelta(days=1)
        # Move back by the number of days there are in a calculated month but return one day to get to first one
        gte_datetime = gte_datetime - timedelta(days=calendar.mdays[gte_datetime.month] - 1)
    # Round the time
    gte_datetime = datetime(gte_datetime.year, gte_datetime.month, 1, tzinfo=now.tzinfo)
    # Calculate month forward
    lt_datetime = gte_datetime + timedelta(days=calendar.mdays[gte_datetime.month])
    return gte_datetime, lt_datetime


class AnalyticsView(TemplateView):
    template_name = 'admin/analytics.html'
    months = [calendar.month_name[i] for i in range(1, 13)]

    @_has_moderation_permission
    def get(self, request, *args, **kwargs):
        classroom_stats = [['all', Classroom.objects.all().count()],]
        user_stats = [['all', IgniteUser.objects.all().count()],]
        unique_projects_started = [['all', Project.objects.filter(registrations__isnull=False).distinct('pk').count()],]
        unique_projects_completed = [['all', Project.objects.filter(registrations__is_completed=True).distinct('pk').count()],]
        projects_started_stats = [['all', ProjectState.objects.all().count()],]
        projects_completed_stats = [['all', ProjectState.objects.filter(is_completed=True).count()],]
        user_that_created_classrooms_stats = [['all', IgniteUser.objects.filter(authored_classrooms__isnull=False).distinct('pk').count()],]
        user_that_created_first_classrooms_stats = [['all', IgniteUser.objects.filter(authored_classrooms__isnull=False).distinct('pk').count()],]
        new_parents_stats = [['all', ChildGuardian.objects.filter(moderator_type=ChildGuardian.MODERATOR_PARENT).distinct('guardian').count()]]
        new_teachers_stats = [['all', ChildGuardian.objects.filter(moderator_type=ChildGuardian.MODERATOR_EDUCATOR).distinct('guardian').count()]]
        for i in range(0, 6):
            gte_datetime, lt_datetime = _helper_get_months_back_date_range(i)

            # classrooms
            overall_classrooms_month = Classroom.objects.filter(
                added__gte=gte_datetime,
                added__lt=lt_datetime
            ).count()
            classroom_stats.append([self.months[gte_datetime.month - 1], overall_classrooms_month])

            # user
            overall_user_month = IgniteUser.objects.filter(
                added__gte=gte_datetime,
                added__lt=lt_datetime
            ).count()
            user_stats.append([self.months[gte_datetime.month - 1], overall_user_month])

            # Projects started
            overall_project_month = Project.objects.filter(
                registrations__added__gte=gte_datetime,
                registrations__added__lt=lt_datetime
            ).distinct('pk').count()
            unique_projects_started.append([self.months[gte_datetime.month - 1], overall_project_month])

            # Projects completed
            overall_completed_project_month = Project.objects.filter(
                registrations__updated__gte=gte_datetime,
                registrations__updated__lt=lt_datetime,
                registrations__is_completed=True
            ).distinct('pk').count()
            unique_projects_completed.append([self.months[gte_datetime.month - 1], overall_completed_project_month])

            # Users that started projects
            overall_users_starting_project = ProjectState.objects.filter(
                added__gte=gte_datetime,
                added__lt=lt_datetime
            ).count()
            projects_started_stats.append([self.months[gte_datetime.month - 1], overall_users_starting_project])

            # Users that completed projects
            overall_users_completed_project_month = ProjectState.objects.filter(
                updated__gte=gte_datetime,
                updated__lt=lt_datetime,
                is_completed=True
            ).count()
            projects_completed_stats.append([self.months[gte_datetime.month - 1], overall_users_completed_project_month])

            # Users that created classrooms
            user_that_created_classroom_month = IgniteUser.objects.filter(
                authored_classrooms__added__gte=gte_datetime,
                authored_classrooms__added__lt=lt_datetime,
            ).distinct('pk').count()
            user_that_created_classrooms_stats.append([self.months[gte_datetime.month - 1], user_that_created_classroom_month])

            # Users that created first classrooms
            user_that_created_classroom_for_first_time_month = IgniteUser.objects.values(
                'pk'  #strict values to GROUP BY these fields only
            ).annotate(
                min_date=Min('authored_classrooms__added')
            ).filter(
                authored_classrooms__isnull=False,
                min_date__gte=gte_datetime,
                min_date__lt=lt_datetime,
            ).count()
            user_that_created_first_classrooms_stats.append(
                [self.months[gte_datetime.month - 1],
                user_that_created_classroom_for_first_time_month]
            )

            # New parents
            overall_new_parents = ChildGuardian.objects.values(
                'guardian'
            ).annotate(
                min_date=Min('added')
            ).filter(
                min_date__gte=gte_datetime,
                min_date__lt=lt_datetime,
                moderator_type=ChildGuardian.MODERATOR_PARENT,
            ).count()
            new_parents_stats.append([self.months[gte_datetime.month-1], overall_new_parents])

            # New teachers
            overall_new_teachers = ChildGuardian.objects.values(
                'guardian'
            ).annotate(
                min_date=Min('added')
            ).filter(
                min_date__gte=gte_datetime,
                min_date__lt=lt_datetime,
                moderator_type=ChildGuardian.MODERATOR_EDUCATOR,
            ).count()
            new_teachers_stats.append([self.months[gte_datetime.month-1], overall_new_teachers])

        classroom_stats.reverse()
        user_stats.reverse()
        unique_projects_started.reverse()
        unique_projects_completed.reverse()
        projects_started_stats.reverse()
        projects_completed_stats.reverse()
        user_that_created_classrooms_stats.reverse()
        user_that_created_first_classrooms_stats.reverse()
        new_parents_stats.reverse()
        new_teachers_stats.reverse()
        kwargs['months'] = self.months
        kwargs['classroom_stats'] = classroom_stats
        kwargs['user_stats'] = user_stats
        kwargs['unique_projects_started'] = unique_projects_started
        kwargs['unique_projects_completed'] = unique_projects_completed
        kwargs['projects_started_stats'] = projects_started_stats
        kwargs['projects_completed_stats'] = projects_completed_stats
        kwargs['user_that_created_classrooms_stats'] = user_that_created_classrooms_stats
        kwargs['user_that_created_first_classrooms_stats'] = user_that_created_first_classrooms_stats
        kwargs['new_parents_stats'] = new_parents_stats
        kwargs['new_teachers_stats'] = new_teachers_stats
        kwargs['title'] = 'Analytics'
        return super(AnalyticsView, self).get(request, *args, **kwargs)


class AnalyticsPopularView(TemplateView):
    template_name = 'admin/popular_analytics.html'
    months = [calendar.month_name[i] for i in range(1, 13)]

    def _filter_sorted_projects(self, counter_name, projects_analytics_qs, projects_order_list):
        """Helper function that filters and sorts the analytics queryset by the projects orderes list, and returns a list of counters."""
        projects_analytics_dict = {
            project.id: getattr(project, counter_name)
            for project in projects_analytics_qs.filter(pk__in=projects_order_list)
        }
        return [projects_analytics_dict.get(x, 0) for x in projects_order_list]

    @_has_moderation_permission
    def get(self, request, *args, **kwargs):
        param_months_back = request.GET.get('months_back', '')
        param_months_back = int(param_months_back) if param_months_back else None
        param_sort_by = request.GET.get('sort_by', 'views')

        # Make projects Qs and querysets:
        views_projects_q = Q(registrations__isnull=False)
        def _annotate_views_projects_qs(qs):
            return qs.only('pk').annotate(
                views=Count('registrations'),
            ).order_by('-views')
        completes_projects_q = Q(registrations__is_completed=True)
        def _annotate_completes_projects_qs(qs):
            return qs.only('pk').annotate(
                completes=Count('registrations'),
            ).order_by('-completes')

        # Get top projects queryset:
        projects_q = None
        if param_sort_by == 'views':
            annotate_projects_qs = _annotate_views_projects_qs
            projects_q = views_projects_q
        elif param_sort_by == 'completes':
            annotate_projects_qs = _annotate_completes_projects_qs
            projects_q = completes_projects_q
        else:
            raise AssertionError('Unknown "sort_by" parameter!')
        if param_months_back is not None:
            # NOTE: Time slices are on the first time viewed.
            #       Views count the first time viewed on that month.
            #       Completes count the first time viewed on that month and completed later.
            param_gte_datetime, param_lt_datetime = _helper_get_months_back_date_range(param_months_back)
            projects_q &= Q(registrations__added__gte=param_gte_datetime)
            projects_q &= Q(registrations__added__lt=param_lt_datetime)
        projects_qs = annotate_projects_qs(Project.objects.filter(projects_q))[:20]
        projects_order_list = [x.pk for x in projects_qs.only('pk')]

        # Gather analytics for each month and overall for all top projects list:
        months_list = []
        projects_analytics_months = []
        default_months_back = 6
        months_back_range = range(0, default_months_back)
        if param_months_back > default_months_back:
            months_back_range.append(param_months_back)
        for i in reversed(months_back_range):
            gte_datetime, lt_datetime = _helper_get_months_back_date_range(i)
            month_name = self.months[gte_datetime.month-1]
            if i > default_months_back:
                month_name += '*'
            months_list.append((month_name, i))
            projects_analytics_months.append([
                (month_name, sub_cols)
                for sub_cols in zip(
                    self._filter_sorted_projects(
                        'views',
                        _annotate_views_projects_qs(
                            Project.objects.filter(
                                views_projects_q,
                                registrations__added__gte=gte_datetime,
                                registrations__added__lt=lt_datetime,
                            )
                        ),
                        projects_order_list
                    ),
                    self._filter_sorted_projects(
                        'completes',
                        _annotate_completes_projects_qs(
                            Project.objects.filter(
                                completes_projects_q,
                                registrations__added__gte=gte_datetime,
                                registrations__added__lt=lt_datetime,
                            )
                        ),
                        projects_order_list
                    )
                )
            ])
        months_list.append(('Overall', None))
        projects_analytics_months.append([
            ('Overall', sub_cols)
            for sub_cols in zip(
                self._filter_sorted_projects(
                    'views',
                    _annotate_views_projects_qs(
                        Project.objects.filter(views_projects_q)
                    ),
                    projects_order_list
                ),
                self._filter_sorted_projects(
                    'completes',
                    _annotate_completes_projects_qs(
                        Project.objects.filter(completes_projects_q)
                    ),
                    projects_order_list
                ),
            )
        ])

        # Attach project data to its analytics months:
        projects_analytics_months_zipped = zip(*projects_analytics_months)
        projects_dict = {
            project.id: {
                'id': project.id,
                'title': project.title,
            } for project in Project.objects.filter(pk__in=projects_order_list)
        }
        projects_analytics = [
            (projects_dict.get(project_id), projects_analytics_months_zipped[i])
            for i, project_id in enumerate(projects_order_list)
        ]

        kwargs['projects_analytics'] = projects_analytics
        kwargs['months_list'] = months_list
        kwargs['months_sub_list'] = [('Views', 'views'), ('Completes', 'completes')]
        kwargs['param_months_back'] = param_months_back
        kwargs['param_sort_by'] = param_sort_by
        kwargs['projectignite_base_url'] = settings.IGNITE_FRONT_END_BASE_URL + 'app/project/'
        kwargs['title'] = 'Popular Projects Analytics'
        return super(AnalyticsPopularView, self).get(request, *args, **kwargs)
