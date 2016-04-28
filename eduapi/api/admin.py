import urllib

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core import urlresolvers
from django.contrib.contenttypes.admin import GenericTabularInline
from django.conf import settings
from django import forms
from django_select2 import media, AutoModelSelect2Field, AutoHeavySelect2Widget
from suit_ckeditor.widgets import CKEditorWidget
from .models import (
    Lesson,
    Step,
    Project,
    Classroom,
    ClassroomState, 
    Review,
    ProjectGroup,
    OwnerDelegate,
)
from .auth.models import IgniteUser, ChildGuardian
from .models.fields import ArrayJSONField


class Select2Form(forms.Form):
    """Defines a form with select2 widgets."""
    class Media:
        js = list(media.get_select2_heavy_js_libs())
        css = {
            'all': list(media.get_select2_css_libs()),
        }


class Select2ModelForm(Select2Form, forms.ModelForm):
    """Defines a model form with select2 widgets."""
    pass


class UserChoices(AutoModelSelect2Field):
    queryset = get_user_model().objects.all()
    search_fields = ['member_id__iexact', 'name__icontains', 'email__icontains', ]
    empty_values=('', )
    def __init__(self, *args, **kwargs):
        new_kwargs = {
            'widget': AutoHeavySelect2Widget(
                select2_options={
                    'width': '220px',
                    'placeholder': 'Lookup %s ...' % get_user_model()._meta.verbose_name,
                }
            ),
        }
        new_kwargs.update(kwargs)
        super(UserChoices, self).__init__(*args, **new_kwargs)

class UserChildChoices(UserChoices):
    queryset = get_user_model().objects.filter(is_child=True)

class UserAdultChoices(UserChoices):
    queryset = get_user_model().objects.filter(is_child=False)

class UserVerifiedAdultChoices(UserChoices):
    queryset = get_user_model().objects.filter(is_child=False, is_verified_adult=True)

class ProjectChoices(AutoModelSelect2Field):
    queryset = Project.objects.origins()
    search_fields = ['title__icontains', ]
    empty_values = ('', )
    def __init__(self, *args, **kwargs):
        new_kwargs = {
            'widget': AutoHeavySelect2Widget(
                select2_options={
                    'width': '220px',
                    'placeholder': 'Lookup %s ...' % Project._meta.verbose_name,
                }
            ),
        }
        new_kwargs.update(kwargs)
        super(ProjectChoices, self).__init__(*args, **new_kwargs)

class ProjectDraftChoices(ProjectChoices):
    queryset = Project.objects_with_drafts.drafts()

class LessonChoices(AutoModelSelect2Field):
    queryset = Lesson.objects.origins()
    search_fields = ['title__icontains', ]
    empty_values = ('', )
    def __init__(self, *args, **kwargs):
        new_kwargs = {
            'widget': AutoHeavySelect2Widget(
                select2_options={
                    'width': '220px',
                    'placeholder': 'Lookup %s ...' % Project._meta.verbose_name,
                }
            ),
        }
        new_kwargs.update(kwargs)
        super(LessonChoices, self).__init__(*args, **new_kwargs)

class LessonDraftChoices(LessonChoices):
    queryset = Lesson.objects.drafts()


# region ReviewInline
class ReviewForm(Select2ModelForm):
    owner = UserChoices(label='Owner')

    class Meta:
        model = Review
        exclude = []
        widgets = {
            'text': forms.Textarea(attrs={'cols': 200, 'rows': 5}),
        }


class ReviewInline(GenericTabularInline):
    model = Review
    # readonly_fields = ('user',)
    extra = 0
    form = ReviewForm
# endregion ReviewInline


# region ChildrenInline
class ChildrenInlineForm(Select2ModelForm):
    child = UserChildChoices(label='Guardian')

    class Meta:
        model = ChildGuardian
        exclude = []


class ChildrenInline(admin.TabularInline):
    form = ChildrenInlineForm
    model = ChildGuardian
    fk_name = 'guardian'
    extra = 0
    verbose_name = 'Child'
    verbose_name_plural = 'Children'
    can_delete = True
# endregion ChildrenInline


# region ChildGuardiansInline
class ChildGuardiansInlineForm(Select2ModelForm):
    guardian = UserVerifiedAdultChoices(label='Guardian')

    class Meta:
        model = ChildGuardian
        exclude = []


class GuardiansInline(admin.TabularInline):
    form = ChildGuardiansInlineForm
    model = ChildGuardian
    fk_name = 'child'
    verbose_name = 'Moderator'
    verbose_name_plural = 'Moderators'
    extra = 0
    can_delete = True
# endregion ChildGuardiansInline


# region DelegatesInline
class DelegatesInlineForm(Select2ModelForm):
    user = UserAdultChoices(label='User')

    class Meta:
        model = OwnerDelegate
        exclude = []


class DelegatesInline(admin.TabularInline):
    form = DelegatesInlineForm
    model = OwnerDelegate
    fk_name = 'owner'
    verbose_name = 'Delegate'
    verbose_name_plural = 'Delegates'
    extra = 0
    can_delete = False
# endregion DelegatesInline


# region DelegatorsInline
class DelegatorsInlineForm(Select2ModelForm):
    owner = UserAdultChoices(label='Owner')

    class Meta:
        model = OwnerDelegate
        exclude = []


class DelegatorsInline(admin.TabularInline):
    form = DelegatorsInlineForm
    model = OwnerDelegate
    fk_name = 'user'
    verbose_name = 'Delegator'
    verbose_name_plural = 'Delegators'
    extra = 0
    can_delete = True
# region DelegatorsInline


@admin.register(ProjectGroup)
class ProjectGroupAdmin(admin.ModelAdmin):
    list_display = ["group_name"]
    search_fields = ['=group_name']


@admin.register(IgniteUser)
class IgniteUserAdmin(admin.ModelAdmin):
    list_display = ['member_id', 'name', 'is_child', 'user_avatar']
    exclude = ['password', ]
    search_fields = ['=member_id', '=name', '=email']
    inlines = (
        ChildrenInline, GuardiansInline,
        DelegatesInline, DelegatorsInline,
    )

    def user_avatar(self, obj):
        if obj.avatar:
            return '<img src="%s" width="40" height="40">' % obj.avatar
        return ''
    user_avatar.allow_tags = True


# region Step
class StepForm(Select2ModelForm):
    lesson = LessonChoices(label='Lesson')

    class Meta:
        model = Step
        exclude = ['instructions_list']


@admin.register(Step)
class StepAdmin(admin.ModelAdmin):
    form = StepForm
    list_display = ["lesson", "order", "description", "id"]
    exclude = ('draft_origin',)
    formfield_overrides = {
        ArrayJSONField: {'widget': forms.Textarea},
    }
# endregion Step


class StepInline(admin.TabularInline):
    model = Step
    fields = ('title', 'order', 'edit_step_link')
    readonly_fields = ['edit_step_link',]
    extra = 0

    def edit_step_link(self, obj):
        if obj.pk:
            # url = urlresolvers.reverse('admin:%s_%s_change' % (obj._meta.app_label, obj._meta.module_name), args=[obj.id])
            url = urlresolvers.reverse('admin:%s_%s_change' % ('api', 'step'), args=[obj.id])
            return '<a href="{0}">{1}</a>'.format(url,"Edit Step")
        return ''
    edit_step_link.allow_tags = True


# region Lesson
class LessonForm(Select2ModelForm):
    project = ProjectChoices(label='Project')

    class Meta:
        model = Lesson
        exclude = []


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    form = LessonForm
    list_display=('title', 'project', 'duration', 'step_count', )
    list_filter=('project__publish_mode', 'duration',)
    search_fields=('id', 'title')
    exclude = ('draft_origin',)
    inlines=(StepInline,)

    def step_count(self, obj):
        return obj.steps.all().count()
# endregion Lesson


class LessonInProjectInline(admin.TabularInline):
    model = Lesson
    fields = ['title', 'order', 'edit_lesson_link',]
    readonly_fields = ['edit_lesson_link',]
    extra = 0

    def edit_lesson_link(self, obj):
        if obj.pk:
            # url = urlresolvers.reverse('admin:%s_%s_change' % (obj._meta.app_label, obj._meta.module_name), args=[obj.id])
            url = urlresolvers.reverse('admin:%s_%s_change' % ('api', 'lesson'), args=[obj.id])
            return '<a href="{0}">{1}</a>'.format(url,"Edit Lesson")
        return ''
    edit_lesson_link.allow_tags = True


# region Project
class ProjectForm(Select2ModelForm):
    owner = UserAdultChoices(label='Owner')
    current_editor = UserAdultChoices(label='Current Editor')

    class Meta:
        model = Project
        exclude = []


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    form = ProjectForm
    list_display=('title', 'id', 'duration', 'age', 'difficulty', 'license', 'publish_mode', 'owner', 'lesson_count', 'review_count', 'has_draft', 'project_link')
    list_filter=('publish_mode', 'duration', 'age', 'difficulty', 'license',)
    search_fields=('id', 'title', 'owner__name')
    readonly_fields = ('has_draft',)
    exclude = ('draft_origin',)
    inlines = (LessonInProjectInline, ReviewInline, )
    formfield_overrides = {
        ArrayJSONField: {'widget': forms.Textarea},
    }


    def get_fieldsets(self, request, obj=None):
        fieldsets = super(ProjectAdmin, self).get_fieldsets(request, obj)
        teacher_info_fieldset = ('Teacher Info', {
            'classes': ('collapse',),
            'fields': ('ngss', 'ccss', 'prerequisites', 'teacher_tips',
                       'four_cs_creativity', 'four_cs_critical', 'four_cs_communication', 'four_cs_collaboration',
                       'teacher_additional_resources', 'teachers_files_list', 'skills_acquired',
                       'learning_objectives', 'grades_range', 'subject', 'technology',),
        })
        fieldsets.append(teacher_info_fieldset)
        for f in teacher_info_fieldset[1]['fields']:
            fieldsets[0][1]['fields'].remove(f)
        return fieldsets

    def lesson_count(self, obj):
        return obj.lessons.all().count()

    def review_count(self, obj):
        return obj.reviews.all().count()

    def has_draft(self, obj):
        return obj.has_draft
    has_draft.boolean = True

    def project_link(self, obj):
        return '<a href="%(url)s" target="_blank">View Project</a>' %{
            'url': settings.IGNITE_FRONT_END_BASE_URL + 'app/project/' + str(obj.id) + '/'
        }
    project_link.allow_tags = True
# endregion Project


# region Classroom
class ClassroomStateInlineForm(Select2ModelForm):
    user = UserChoices(label='User')

    class Meta:
        model = ClassroomState
        exclude = []


class ClassroomStateInline(admin.TabularInline):
    form = ClassroomStateInlineForm
    model = ClassroomState
    extra = 0


class ClassroomForm(Select2ModelForm):
    owner = UserAdultChoices(label='Owner')

    class Meta:
        model = Classroom
        exclude = []


@admin.register(Classroom)
class ClassroomAdmin(admin.ModelAdmin):
    form = ClassroomForm
    list_display=('title','owner','card', 'student_count')
    inlines=(ClassroomStateInline,)
    formfield_overrides = {
        ArrayJSONField: {'widget': forms.Textarea},
    }

    def student_count(self, obj):
        return obj.students.all().count()

    def card(self, obj):
        if obj.card_image:
            return '<img src="%s" width="40" height="40">' % obj.card_image
        return ''
    card.allow_tags = True

# endregion Classroom
