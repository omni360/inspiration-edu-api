import re

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.views.generic import TemplateView
from django.utils.functional import cached_property
from django.conf import settings

from api.tasks import send_mail_template

from ..models import IgniteUser, Project
from marketplace.models import Purchase

from api.admin import UserChoices, Select2Form
from api.custom_admin.guardian_moderation import _has_moderation_permission


class AddNewUserForm(Select2Form):
    add_new_user = UserChoices(label='Add New User')

    class Meta:
        fields = ('add_new_user',)


class ArduinoKitPermsView(TemplateView):
    template_name = 'admin/arduino_kit_perms.html'

    @cached_property
    def user_form(self):
        return AddNewUserForm()

    @cached_property
    def projects_list(self):
        # Note: There are projects with lock='Bundle', that are allowed only when purchased.
        #       settings.ARDUINO_RPOJECTS_IDS define list of (usually) bundled projects that are part of Arduino.
        #       Here we take only the bundled projects of Arduino (and not all bundled projects)!
        return [{
            'id': project.id,
            'title': project.title
        } for project in Project.objects.filter(
            lock=Project.BUNDLED,
            id__in=settings.ARDUINO_PROJECTS_IDS
        ).order_by('id')]

    @cached_property
    def projects_ids_list(self):
        return [x['id'] for x in self.projects_list]

    def get_context_data(self, **kwargs):
        context = super(ArduinoKitPermsView, self).get_context_data(**kwargs)
        context.update({
            'title': 'Arduino Kit permissions',
            'arduino_media': self.user_form.media,
            'arduino_purchase_permissions': Purchase.PERMISSION_TYPES,
            'arduino_purchase_permission_teacher': Purchase.TEACH_PERM,
            'arduino_projects': self.projects_list,
            'arduino_add_new_user_field': self.user_form['add_new_user'],
            'arduino_action': getattr(self, 'action', None),
            'arduino_users_perms': getattr(self, 'users_perms', None),
        })
        return context

    @_has_moderation_permission
    def dispatch(self, request, *args, **kwargs):
        return super(ArduinoKitPermsView, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        return super(ArduinoKitPermsView, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        # Action data:
        self.action = request.POST.get('action', None)

        # Get users who should get permissions:
        _helper_set = set()  # helper set to remove duplicates from list, keeping the original order (Note set() is not ordered)
        users_ids = [x for x in request.POST.getlist('users_ids[]', []) if not (x in _helper_set or _helper_set.add(x))]
        users_ids = map(lambda x: int(x), users_ids)
        users_objs_dict = {u.id: u for u in IgniteUser.objects.filter(pk__in=users_ids).only('id', 'name', 'email')}
        self.users_perms = []
        for user_id in users_ids:
            user_perm = users_objs_dict.get(user_id, None)
            if user_perm:
                self.users_perms.append({
                    'id': user_perm.id,
                    'name': user_perm.name,
                    'email': user_perm.email,
                    'permission': request.POST.get('users_perms[%s][permission]'%user_perm.id, Purchase.TEACH_PERM),
                    'send_email': request.POST.get('users_perms[%s][send_email]'%user_perm.id, '') == 'true',
                    'projects': map(lambda x: int(x), request.POST.getlist('users_perms[%s][projects][]'%user_perm.id, [])),
                    'confirmed': request.POST.get('users_perms[%s][confirmed]'%user_perm.id, '') == 'true',
                })

        # Add new user to the list:
        if self.action == 'add':
            try:
                new_user = IgniteUser.objects.get(pk=request.POST['add_new_user'])
            except IgniteUser.DoesNotExist:
                messages.add_message(request, messages.ERROR, 'User does not exist!')
            else:
                if new_user.id in users_objs_dict:
                    messages.add_message(request, messages.ERROR, 'User "%s" was already selected and is in the list.' % new_user.name)
                else:
                    self.users_perms.append({
                        'id': new_user.id,
                        'name': new_user.name,
                        'permission': Purchase.TEACH_PERM,
                        'send_email': False,
                        'projects': self.projects_ids_list,
                        'confirmed': False,
                    })

        # Confirm permissions for all users:
        elif self.action == 'confirm':
            notify_users_list = []
            for user_perm in self.users_perms:
                if not user_perm.get('confirmed', False):
                    for project_id in user_perm['projects']:
                        try:
                            purchase = Purchase.objects.get(user_id=user_perm['id'], project_id=project_id)
                        except Purchase.DoesNotExist:
                            purchase = None
                        if purchase:
                            # If permission exists is lower than the permission wanted, then upgrade permission (otherwise keep existing):
                            if purchase.permission != user_perm['permission'] and user_perm['permission'] == Purchase.TEACH_PERM:
                                purchase.permission = user_perm['permission']
                                purchase.save()
                        else:
                            # If no purchase found, then create with the wanted permission:
                            purchase = Purchase(
                                user_id=user_perm['id'],
                                project_id=project_id,
                                permission=user_perm['permission'],
                            )
                            purchase.save()
                    if user_perm['send_email']:
                        notify_users_list.append(user_perm)
                    user_perm['confirmed'] = True

            # Send the Arduino Purchase Notification email to the users that were checked on.
            if notify_users_list:
                send_mail_template.delay(
                    settings.EMAIL_TEMPLATES_NAMES['ARDUINO_PURCHASE_NOTIFICATION'],
                    [{
                        'recipient': {
                            'name': user['name'],
                            'address': user['email'],
                        }
                    } for user in notify_users_list],
                )

        return super(ArduinoKitPermsView, self).get(request, *args, **kwargs)
