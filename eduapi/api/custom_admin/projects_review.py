from django import forms
from django.contrib import admin
from django.contrib import messages
from django.conf.urls import url
from django.conf import settings
from django.core.urlresolvers import reverse
from django.db.models import Q, Case, When
from django.contrib.admin.utils import quote
from django.http import response
from django.template.response import TemplateResponse
from django.utils.html import escape
from django.utils.timezone import now as utc_now
from django.utils.safestring import mark_safe
import re

from api.models import Project, Notification
from editor_tools.tools import BadWordsTool


class ProjectDeclineForm(forms.Form):
    review_feedback = forms.CharField(widget=forms.Textarea())

    def clean(self):
        cleaned_data = super(ProjectDeclineForm, self).clean()
        review_feedback = cleaned_data.get("review_feedback")

        if not review_feedback:
            raise forms.ValidationError(
                "You have to provide feedback if you are going to decline this project."
            )
        return cleaned_data



class ProjectsReviewAdmin(admin.ModelAdmin):
    model = Project
    list_display=('title', 'owner', 'publish_mode_with_draft', 'min_publish_date_formatted', 'description_inline', 'external_view_link',)
    list_filter=('min_publish_date',)
    search_fields=('id', 'title', 'owner__name',)
    actions = None
    ordering = ('-updated',)
    form = ProjectDeclineForm

    project_review_change_template = 'admin/project_review_change.html'

    def get_changelist(self, request, **kwargs):
        cl = super(ProjectsReviewAdmin, self).get_changelist(request, **kwargs)
        admin_site = self.admin_site
        class ProjectsReviewChangeList(cl):
            def url_for_result(self, result):
                pk = getattr(result, self.pk_attname)
                return reverse('%s:project-review-change' % (admin_site.name,),
                               args=(quote(pk),),
                               current_app=self.model_admin.admin_site.name)
            def get_ordering(self, request, queryset):
                #always order that published projects with drafts will be first.
                ordering = [Case(When(draft_object__isnull=False, then=0))]
                ordering.extend(super(ProjectsReviewChangeList, self).get_ordering(request, queryset))
                return ordering
        return ProjectsReviewChangeList

    def get_urls(self):
        urlpatterns = [
            url(r'^$', self.admin_site.admin_view(self.changelist_view), name='projects-review-changelist'),
            url(r'^(.+)/$', self.project_review_change_view, name='project-review-change'),
        ]
        return urlpatterns

    def get_queryset(self, request):
        qs = super(ProjectsReviewAdmin, self).get_queryset(request)
        qs = qs.filter(
            # project in review mode
            Q(publish_mode=Project.PUBLISH_MODE_REVIEW) |
            # project in published mode with draft object in review mode
            Q(publish_mode=Project.PUBLISH_MODE_PUBLISHED, draft_object__publish_mode=Project.PUBLISH_MODE_REVIEW)
        )
        return qs

    def has_add_permission(self, request):
        return False
    def has_delete_permission(self, request, obj=None):
        return False
    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj:
            return obj.can_publish(request.user)
        return False

    def _get_project_external_view_url(self, obj):
        url = settings.IGNITE_FRONT_END_BASE_URL + 'app/project/%s/' %(obj.pk,)
        if obj.publish_mode == Project.PUBLISH_MODE_PUBLISHED and obj.has_draft:
            url += '?withDraftChanges=true'
        return url

    def _get_bad_words_list_to_display_for_project(self, project):
        bad_words_issues_keys_to_display_map = {
            'project': {
                'title': 'Project Title',
                'description': 'Project Description',
                'teacher_additional_resources': 'Project Teacher Info: Additional Resources',
                'prerequisites': 'Project Teacher Info: Prerequisites',
                'teacher_tips': 'Project Teacher Info: Tips',
                'four_cs_creativity': 'Project Teacher Info: 4cs: Creativity',
                'four_cs_critical': 'Project Teacher Info: 4cs: Critical',
                'four_cs_communication': 'Project Teacher Info: 4cs: Communication',
                'four_cs_collaboration': 'Project Teacher Info: 4cs: Collaboration',
                'skills_acquired': 'Project Teacher Info: Skills Acquired',
                'learning_objectives': 'Project Teacher Info: Learning Objectives',
            },
            'lesson': {
                'title': 'Lesson Title',
                'application_blob_description': 'Lesson Video Description',
            },
            'step': {
                'title': 'Step Title',
                'description': 'Step Description',
            },
            'instruction': {
                'description': 'Instruction Description',
                'hint': 'Instruction Hint',
            },
        }

        def _make_bad_words_issues_list(type_name, bad_words_issues, ref_title):
            def _add_higlighted_sentence(case):
                bad_word_p = re.compile(
                    r'(%s)' % '|'.join([
                        re.escape(s)
                        for s in sorted(case['bad_words'], key=lambda x: (-len(x), x))  #sort bad words by length and alphabetic to split match longer words first
                    ]),
                    flags=re.IGNORECASE
                )
                sentence_bad_words_portions = bad_word_p.split(case['sentence'])
                sentence_bad_words_portions = [
                    escape(portion) if i%2==0 else '<span class="bad-word-highlight">%s</span>' % escape(portion)
                    for i, portion in enumerate(sentence_bad_words_portions)
                ]
                case['safe_highlighted_sentence'] = mark_safe(''.join(sentence_bad_words_portions))
                return case
            return [{
                    'ref_key': bad_words_issues_keys_to_display_map[type_name][issue_key],
                    'ref_title': ref_title,
                    'cases': [_add_higlighted_sentence(case) for case in bad_words_issues[issue_key]],
                } for issue_key, issue_key_display in bad_words_issues_keys_to_display_map[type_name].items() if issue_key in bad_words_issues]

        # Check bad words and prepare for displaying:
        bad_words_list = []
        project_bad_words = BadWordsTool().bad_words_in_project(project)
        if project_bad_words:
            lessons_bad_words = project_bad_words['issues'].pop('lessons', [])
            bad_words_list += _make_bad_words_issues_list('project', project_bad_words['issues'], '')
            for lesson_bad_words in lessons_bad_words:
                steps_bad_words = lesson_bad_words['issues'].pop('steps', [])
                lesson_ref_title = lesson_bad_words['lesson_title']
                bad_words_list += _make_bad_words_issues_list('lesson', lesson_bad_words, lesson_ref_title)
                for step_bad_words in steps_bad_words:
                    instructions_bad_words = step_bad_words['issues'].pop('instructions', [])
                    step_ref_title = 'Step #%s of Lesson: %s' % (step_bad_words['step_order']+1, lesson_ref_title)
                    bad_words_list += _make_bad_words_issues_list('step', step_bad_words['issues'], step_ref_title)
                    for instruction_bad_words in instructions_bad_words:
                        instruction_ref_title = 'Instruction #%s of %s' % (instruction_bad_words['instruction_order']+1, step_ref_title)
                        bad_words_list += _make_bad_words_issues_list('instruction', instruction_bad_words['issues'], instruction_ref_title)

        return bad_words_list


    def external_view_link(self, obj):
        return '<a href="%s" target="_blank">View Project <i class="icon-share icon-alpha75"></i></a>' %(self._get_project_external_view_url(obj),)
    external_view_link.short_description = 'View in ProjectIgnite (external)'
    external_view_link.allow_tags = True

    def min_publish_date_formatted(self, obj):
        if obj.min_publish_date:
            return obj.min_publish_date.strftime('%Y-%m-%d %H:%M')
        return None
    min_publish_date_formatted.short_description = 'Minimum publish date'
    min_publish_date_formatted.admin_order_field = 'min_publish_date'

    def description_inline(self, obj):
        # return '<div style="max-height:100px; overflow:auto;">%s</div>' % obj.description
        return (
            '<small>[<a href="#project-in-review-%(id)s-description" data-toggle="collapse">show/hide description</a>]</small>'
            '<div id="project-in-review-%(id)s-description" class="collapse"><div style="max-height:250px; overflow:auto; border:1px solid #ccc;">%(description)s</div></div>'
        ) % {
            'id': obj.id,
            'description': obj.description
        }
    description_inline.short_description = 'Description'
    description_inline.allow_tags = True

    def publish_mode_with_draft(self, obj):
        publish_mode_text = dict(Project.PUBLISH_MODES)[obj.publish_mode]
        if obj.publish_mode == Project.PUBLISH_MODE_PUBLISHED and obj.has_draft:
            return '%s <small class="help-inline">[New Version]</small>' % (publish_mode_text,)
        return publish_mode_text
    publish_mode_with_draft.short_description = 'Publish Mode'
    publish_mode_with_draft.admin_order_field = 'publish_mode'
    publish_mode_with_draft.allow_tags = True


    def project_review_change_view(self, request, object_id):
        # Get project.
        project = self.get_object(request, object_id)
        if project is None:
            raise response.Http404('Project object with primary key %(key)r does not found in review mode.' % {
                'key': escape(object_id)
            })

        # Action handling
        has_changed_publish_mode = False
        if request.method == 'POST':
            form = self.form({'review_feedback': request.POST.get('review_feedback')})
            change_publish_mode = request.POST.get('changePublishMode')

            #if project origin is published and has draft, then refer to project draft:
            project_origin = project
            if project_origin.publish_mode == Project.PUBLISH_MODE_PUBLISHED and project_origin.has_draft:
                project = project.draft_get()

            old_publish_mode = project.publish_mode
            if change_publish_mode == Project.PUBLISH_MODE_READY:
                has_changed_publish_mode = True
                # If minimum publish date has passed, then move project_edit to published mode
                min_publish_date = getattr(project, 'min_publish_date', None)
                if not min_publish_date or min_publish_date < utc_now():
                    # New unpublished project - save as published:
                    if not project.is_draft:
                        project.publish_mode = Project.PUBLISH_MODE_PUBLISHED
                        project.save()
                        project.notify_owner(
                            'project_publish_mode_change_by_target',
                            {
                                'target': request.user,
                                'description': 'Project "%s" has been approved and published by the Project Ignite team.' %(project.title,),
                                'publishMode': project.publish_mode,
                                'oldPublishMode': old_publish_mode,
                                'publishDate': project.publish_date.strftime('%Y-%m-%d %H:%M'),
                            },
                            send_mail_with_template='IGNITE_notification_publish_mode_change',
                        )
                    # Draft of published project - apply changes from draft to origin:
                    else:
                        change_publish_mode = Project.PUBLISH_MODE_PUBLISHED
                        notify_kwargs = {
                            'target': request.user,
                            'description': 'The changes to project "%s" have been approved and published by the Project Ignite team.' %(project.title,),
                            'publishMode': project_origin.publish_mode,
                            'publishDate': project_origin.publish_date.strftime('%Y-%m-%d %H:%M'),
                            'draftPublishMode': change_publish_mode,
                            'draftOldPublishMode': old_publish_mode,
                            'draftDiff': {
                                'id': project_origin.id,
                                'title': project_origin.draft_object.title,
                                'diffFields': project_origin.draft_diff_fields(),
                                'lessons': [{
                                    'id': lesson.id,
                                    'title': lesson.draft_object.title,
                                    'diffFields': lesson.draft_diff_fields(),
                                    'steps': [{
                                        'id': step.id,
                                        'title': step.draft_object.title,
                                        'diffFields': step.draft_diff_fields(),
                                    } for step in lesson.steps.all() if step.has_draft]
                                } for lesson in project_origin.lessons.all() if lesson.has_draft]
                            }
                        }
                        #apply draft:
                        project.draft_apply()
                        project.draft_discard()
                        #notify owner when draft was applied:
                        notify_kwargs['draftAppliedDate'] = project_origin.updated.strftime('%Y-%m-%d %H:%M')
                        project_origin.notify_owner(
                            'project_draft_mode_changed_by_target',
                            notify_kwargs,
                            send_mail_with_template='IGNITE_notification_publish_mode_change',
                        )
                else:
                    #Note: project draft can not use min_publish_date, therefore only origin project is used here.
                    project.publish_mode = Project.PUBLISH_MODE_READY
                    project.publish_date = None
                    project.save()
                    project.notify_owner(
                        'project_publish_mode_change_by_target',
                        {
                            'target': request.user,
                            'description': 'Project "%s" has been approved by the Ignite Team and will be published on %s UTC.' %(project.title, project.min_publish_date.strftime('%Y-%m-%d %H:%M')),
                            'publishMode': project.publish_mode,
                            'oldPublishMode': old_publish_mode,
                        },
                        send_mail_with_template='IGNITE_notification_publish_mode_change',
                    )

            if change_publish_mode == Project.PUBLISH_MODE_EDIT:
                if form.is_valid():
                    has_changed_publish_mode = True
                    project.publish_mode = Project.PUBLISH_MODE_EDIT
                    project.publish_date = None
                    project.save()
                    review_feedback_text = form.cleaned_data.get('review_feedback', '').replace("\r\n", "<br>")
                    if not project.is_draft:
                        project.notify_owner(
                            'project_publish_mode_change_by_target_with_feedback',
                            {
                                'target': request.user,
                                'description': 'Project "%s" has been declined by the Project Ignite team%s.' %(project.title, ' with feedback' if review_feedback_text else ''),
                                'publishMode': project.publish_mode,
                                'oldPublishMode': old_publish_mode,
                                'feedback': review_feedback_text,
                            },
                            send_mail_with_template='IGNITE_notification_publish_mode_change',
                        )
                    else:
                        notify_kwargs = {
                            'target': request.user,
                            'description': 'The changes to project "%s" have been declined by the Project Ignite team%s.' %(project.title, ' with feedback' if review_feedback_text else ''),
                            'publishMode': project_origin.publish_mode,
                            'publishDate': project_origin.publish_date.strftime('%Y-%m-%d %H:%M'),
                            'draftPublishMode': change_publish_mode,
                            'draftOldPublishMode': old_publish_mode,
                            'draftDiff': {
                                'id': project_origin.id,
                                'title': project_origin.draft_object.title,
                                'diffFields': project_origin.draft_diff_fields(),
                                'lessons': [{
                                    'id': lesson.id,
                                    'title': lesson.draft_object.title,
                                    'diffFields': lesson.draft_diff_fields(),
                                    'steps': [{
                                        'id': step.id,
                                        'title': step.draft_object.title,
                                        'diffFields': step.draft_diff_fields(),
                                    } for step in lesson.steps.all() if step.has_draft]
                                } for lesson in project_origin.lessons.all() if lesson.has_draft]
                            },
                            'feedback': review_feedback_text,
                        }
                        #notify owner when draft was failed:
                        project_origin.notify_owner(
                            'project_draft_mode_changed_by_target_with_feedback',
                            notify_kwargs,
                            send_mail_with_template='IGNITE_notification_publish_mode_change',
                        )

            #restore reference of project to origin:
            project = project_origin

        else:
            form = self.form()

        # Project notifications
        project_notifications = Notification.objects.filter(
            recipient=project.owner,
            actor_content_type__model=Project._meta.model_name,
            actor_object_id=project.pk,
            verb__in=[
                'project_publish_mode_change_by_target', 'project_publish_mode_change_by_target_with_feedback',
                'project_draft_mode_changed_by_target', 'project_draft_mode_changed_by_target_with_feedback',
            ],
        ).order_by('timestamp')

        context = {
            'project': project,
            'project_external_view_url': self._get_project_external_view_url(project),
            'has_changed_publish_mode': has_changed_publish_mode,
            'project_notifications': project_notifications,
            'publish_modes': dict(Project.PUBLISH_MODES),
            'form': form,
            'bad_words_list': self._get_bad_words_list_to_display_for_project(project),
        }

        return TemplateResponse(
            request=request,
            template=self.project_review_change_template,
            context=context,
        )
