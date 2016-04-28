from django import forms
from django.contrib import messages
from django.views.generic import TemplateView
from django.utils.functional import cached_property

from django_select2 import AutoHeavySelect2Widget

from ..auth.oxygen_operations import OxygenOperations, _OxygenRequestFailed
from ..models import IgniteUser

from api.admin import UserChoices, Select2Form

from guardian_moderation import _has_moderation_permission


class ChildUserChoices(UserChoices):
    queryset = IgniteUser.objects.filter(is_child=True)
    search_fields = ['member_id__iexact', 'name__istartswith', 'email__iexact',]
    def __init__(self, *args, **kwargs):
        new_kwargs = {
            'widget': AutoHeavySelect2Widget(
                select2_options={
                    'width': '220px',
                    'placeholder': 'Name, member ID, exact email ...',
                }
            ),
        }
        new_kwargs.update(kwargs)
        super(UserChoices, self).__init__(*args, **new_kwargs)


class PasswordForm(forms.Form):
    new_password = forms.RegexField(label='New Password', max_length=50, min_length=8, required=True, regex='\S+')


class SearchChildForm(Select2Form):
    child_id = ChildUserChoices(label='Search Child')

    class Meta:
        fields = ('child_id',)


class ChildPasswordResetView(TemplateView):
    template_name = 'admin/child_password_reset.html'

    @cached_property
    def search_child_form(self):
        return SearchChildForm()

    @_has_moderation_permission
    def dispatch(self, request, *args, **kwargs):
        self.child = None

        # Try get the child:
        child_id = self.request.GET.get('child_id', None)
        if child_id is not None:
            try:
                child = IgniteUser.objects.get(pk=child_id)
            except IgniteUser.DoesNotExist:
                messages.add_message(self.request, messages.ERROR, 'Child is not found!')
            else:
                if not child.is_child:
                    messages.add_message(self.request, messages.ERROR, 'This user is not a child!')
                else:
                    self.child = child

        return super(ChildPasswordResetView, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        form = PasswordForm(request.POST)
        self.error_message = ''
        if self.child and form.is_valid():
            oxygen_ops = OxygenOperations()
            try:
                response = oxygen_ops.reset_child_password(child=self.child,
                                                           guardian=self.child.guardians.all()[0],
                                                           password=form.cleaned_data['new_password'])
                if response:
                    self.successful_change = True
                    messages.add_message(request, messages.SUCCESS, 'Password change successful!')
            except _OxygenRequestFailed as e:
                self.error_message = e.oxygen_error_desc
            except Exception as e:
                self.error_message = e.message
        else:
            self.error_message = 'Allowed password length is 8-50 chars'
        return super(ChildPasswordResetView, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ChildPasswordResetView, self).get_context_data(**kwargs)
        context.update({
            'title': 'Child Password Reset',
            'moderation_media': self.search_child_form.media,
            'search_child_field': self.search_child_form['child_id'],
            'child': getattr(self, 'child', None),
            'error_message': getattr(self, 'error_message', None),
            'successful_change': getattr(self, 'successful_change', None),
        })
        return context
