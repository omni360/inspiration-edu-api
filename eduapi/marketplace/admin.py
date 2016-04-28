from django.contrib import admin
from django.conf import settings
from django.forms import ModelForm

from .models import Purchase
from api.models import Project
from api.admin import Select2ModelForm, ProjectChoices, UserChoices


class ProjectPurchasableChoices(ProjectChoices):
    queryset = Project.objects.filter(id__in=settings.ARDUINO_PROJECTS_IDS)


class PurchaseForm(Select2ModelForm):
    project = ProjectPurchasableChoices(label='Purchasable Project')
    user = UserChoices(label='User')


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    form = PurchaseForm
    list_display = ['user_name', 'project_title', 'permission']

    def user_name(self, obj):
        return obj.user.name

    def project_title(self, obj):
        return obj.project.title
