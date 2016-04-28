import re

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.views.generic import TemplateView
from django.utils.functional import cached_property
from django.db.models import Q

from django_select2 import AutoHeavySelect2Widget

from ..auth.oxygen_operations import OxygenOperations
from ..models import IgniteUser, ChildGuardian

from api.admin import UserChoices, Select2Form


class ModeratorUserChoices(UserChoices):
    queryset = IgniteUser.objects.filter(is_child=False)
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


class SearchModeratorForm(Select2Form):
    guardian_id = ModeratorUserChoices(label='Search Guardian')

    class Meta:
        fields = ('guardian_id',)


def _has_moderation_permission(func):
    def inner(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied
        return func(self, request, *args, **kwargs)
    return inner


class GuardianModerationView(TemplateView):
    template_name = 'admin/guardian_moderation.html'

    @cached_property
    def search_moderator_form(self):
        return SearchModeratorForm()

    def _find_users(self, sr, qs=None):
        qs = qs if qs else IgniteUser.objects.all()
        sr = sr.lower()
        return qs.filter(
            Q(member_id__iexact=sr) |
            Q(name__istartswith=sr) |
            Q(email__iexact=sr)
        )

    def _make_user_output(self, user_obj, user_oxygen_response=None):
        user_output = {
            'id': user_obj.id,
            'name': user_obj.name,
            'isChild': user_obj.is_child,
            'guardians': [g.id for g in user_obj.guardians.all()],
        }
        if user_oxygen_response is not None:
            user_output['oxygen_response'] = {
                'state': user_oxygen_response['state'],
                'message': user_oxygen_response['message'],
            }
            child_guardian_obj = user_oxygen_response.get('child_guardian')
        else:
            child_guardian_obj = ChildGuardian.objects.filter(child=user_obj, guardian=self.guardian).first()
        if child_guardian_obj is not None:
            user_output['moderator_type'] = child_guardian_obj.moderator_type
        return user_output

    def get_context_data(self, **kwargs):
        context = super(GuardianModerationView, self).get_context_data(**kwargs)
        context.update({
            'title': 'COPPA Moderation (Parental\\Institutional)',
            'moderator_types_choices': ChildGuardian.MODERATOR_TYPE_CHOICES,
            'moderation_media': self.search_moderator_form.media,
            'search_guardian_field': self.search_moderator_form['guardian_id'],
            'guardian': getattr(self, 'guardian', None),
            'guardians_found': getattr(self, 'guardians_found', None),
            'post_operation': getattr(self, 'post_operation', None),
            'moderator_type': getattr(self, 'moderator_type', ChildGuardian.MODERATOR_EDUCATOR),
            'new_children_bulk': getattr(self, 'new_children_bulk', None),
            'new_children_search_output': getattr(self, 'new_children_search_output', None),
            'new_children_confirm_output': getattr(self, 'new_children_confirm_output', None),
        })
        return context

    @_has_moderation_permission
    def dispatch(self, request, *args, **kwargs):
        self.guardian = None

        # Try get the guardian:
        guardian_id = request.GET.get('guardian_id', None)
        if guardian_id is not None:
            try:
                guardian = IgniteUser.objects.get(pk=guardian_id)
            except IgniteUser.DoesNotExist:
                messages.add_message(request, messages.ERROR, 'Moderator is not found!')
            else:
                if guardian.is_child:
                    messages.add_message(request, messages.ERROR, 'Moderator must be an adult!')
                else:
                    self.guardian = guardian

        return super(GuardianModerationView, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if self.guardian:
            self.post_operation = request.GET.get('op', None)
            # process children bulk text input, then lookup for children and output the list:
            if self.post_operation == 'bulk':
                self.new_children_bulk = request.POST.get('newChildrenBulk', '')
                self.moderator_type = request.POST.get('moderatorType')
                new_children_lookups = [ch_lookup.strip() for ch_lookup in re.compile(r'[\n,]').split(self.new_children_bulk) if ch_lookup.strip()]
                new_children_searches = sorted(
                    [
                        (new_child_lookup, list(self._find_users(new_child_lookup)))
                        for new_child_lookup
                        in new_children_lookups
                    ],
                    key=lambda x:len(x[1]),
                    #sort lengths >1, 1, 0 (duplicates founds, single found, not found)
                    cmp=lambda x, y: 0 if x==y else -1 if x<y else 1,
                    reverse=True
                )
                if not new_children_searches:
                    messages.add_message(request, messages.WARNING, 'Nothing was entered for children lookup.')
                else:
                    self.new_children_search_output = [(ch_lookup, [self._make_user_output(ch_obj) for ch_obj in ch_list]) for ch_lookup, ch_list in new_children_searches]
                    #check if guardian is verified adult:
                    if not self.guardian.is_verified_adult:
                        messages.add_message(request, messages.WARNING, 'The moderator is not marked as a verified adult. Once a child is added to this moderator, it will become a verified adult.')

            # process confirming children list, then add children and output the results:
            elif self.post_operation == 'confirm':
                new_children_ids = request.POST.getlist('newChildrenIds[]', [])
                self.moderator_type = request.POST.get('moderatorType')
                #get new children only, excluding existing children of the guardian:
                new_children = IgniteUser.objects\
                    .filter(id__in=new_children_ids)
                    # .exclude(id__in=[x.id for x in self.guardian.children.all()])
                new_children = list(new_children)  #materialize queryset
                if new_children:
                    #use OxygenOperations to add children to the guardian:
                    oxygen_operations = OxygenOperations()
                    try:
                        oxygen_op_result = oxygen_operations.add_guardian_children(
                            self.guardian,
                            {
                                self.moderator_type: new_children
                            }
                        )
                    except oxygen_operations.OxygenRequestFailed as exc:
                        messages.add_message(request, messages.ERROR, exc.message)
                        self.new_children_confirm_output = None
                    else:
                        #make new children output:
                        self.new_children_confirm_output = [self._make_user_output(u['child'], u) for _,u in oxygen_op_result[self.moderator_type].items()]

                else:
                    messages.add_message(request, messages.WARNING, 'No new children were given.')
                    self.new_children_confirm_output = []

        return super(GuardianModerationView, self).get(request, *args, **kwargs)
