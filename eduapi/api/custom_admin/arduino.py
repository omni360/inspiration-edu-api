import calendar
from datetime import datetime
from django.views.generic import TemplateView
from django.utils.timezone import now as utc_now
from django.conf import settings

from api.models import ProjectState, Project, Purchase

from guardian_moderation import _has_moderation_permission

class ArduinoView(TemplateView):
    template_name = 'admin/arduino.html'
    months = [calendar.month_name[i] for i in range(1, 13)]
    arduino_free_projects_ids = [52]

    @_has_moderation_permission
    def get(self, request, *args, **kwargs):
        now = utc_now()
        month_numerical = range(1, 13)
        arduino_purchases = [['all', Purchase.objects.filter(permission=Purchase.TEACH_PERM).distinct('user').count()]]
        users_starting_arduino_projects_stats = [['all', ProjectState.objects.filter(project_id__in=settings.ARDUINO_PROJECTS_IDS).count()],]
        users_starting_arduino_free_projects_stats = [['all', ProjectState.objects.filter(project_id__in=self.arduino_free_projects_ids).count()]]
        for i in range(0, 6):
            gte_month_number = month_numerical[now.month - i - 1]
            lt_month_number = month_numerical[(now.month - i) % 12]
            gte_year = now.year if now.month > i else now.year - 1
            lt_year = now.year if now.month >= i else now.year - 1
            gte_datetime = datetime(gte_year, gte_month_number, 1, tzinfo=now.tzinfo)
            lt_datetime = datetime(lt_year, lt_month_number, 1, tzinfo=now.tzinfo)

            # Arduino purchases
            overall_arduino_purchases = Purchase.objects.filter(
                added__gte=gte_datetime,
                added__lt=lt_datetime,
                permission=Purchase.TEACH_PERM,
            ).distinct(
                'user'
            ).count()
            arduino_purchases.append([self.months[gte_month_number-1], overall_arduino_purchases])

            # Users starting Arduino projects
            overall_users_starting_arduino_projects_stats = ProjectState.objects.filter(
                added__gte=gte_datetime,
                added__lt=lt_datetime,
                project_id__in=settings.ARDUINO_PROJECTS_IDS
            ).count()
            users_starting_arduino_projects_stats.append([self.months[gte_month_number-1], overall_users_starting_arduino_projects_stats])

            # Users starting Arduino free projects
            overall_users_starting_arduino_free_projects_stats = ProjectState.objects.filter(
                added__gte=gte_datetime,
                added__lt=lt_datetime,
                project_id__in=self.arduino_free_projects_ids
            ).count()
            users_starting_arduino_free_projects_stats.append([self.months[gte_month_number-1], overall_users_starting_arduino_free_projects_stats])

        arduino_purchases.reverse()
        users_starting_arduino_projects_stats.reverse()
        users_starting_arduino_free_projects_stats.reverse()
        kwargs['months'] = self.months
        kwargs['arduino_free_projects_ids'] = self.arduino_free_projects_ids
        kwargs['arduino_purchases'] = arduino_purchases
        kwargs['users_starting_arduino_projects_stats'] = users_starting_arduino_projects_stats
        kwargs['users_starting_arduino_free_projects_stats'] = users_starting_arduino_free_projects_stats

        arduino_projects_stats = []
        for arduino_project_id in settings.ARDUINO_PROJECTS_IDS:
            arduino_project_obj = Project.objects.get(id=arduino_project_id)
            arduino_projects_stats.append({
                'id': arduino_project_obj.id,
                'title': arduino_project_obj.title,
                'total_users_started': arduino_project_obj.registrations.count(),
                'total_users_completed': arduino_project_obj.registrations.filter(is_completed=True).count(),
            })
        kwargs['arduino_projects_stats'] = arduino_projects_stats

        kwargs['title'] = 'Arduino Analytics'

        return super(ArduinoView, self).get(request, *args, **kwargs)
