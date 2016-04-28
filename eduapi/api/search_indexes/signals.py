from haystack.signals import RealtimeSignalProcessor
from haystack.query import SearchQuerySet
from haystack.exceptions import NotHandled

from api.models import Project, Lesson, IgniteUser


class IgniteSignalProcessor(RealtimeSignalProcessor):
    index_models = [Project, Lesson, IgniteUser]  # explicitly define models that influence the index by haystack

    def handle_save(self, sender, instance, **kwargs):
        if sender not in self.index_models:
            return

        # If IgniteUser was saved and changed name, then update all its authored projects owner_name:
        if sender == IgniteUser:
            owner_projects_qs = Project.objects.filter(owner=instance)
            base_owner_projects_sq = SearchQuerySet()
            base_owner_projects_sq = base_owner_projects_sq.models(Project)
            for owner_project_instance in owner_projects_qs:
                # get owner project from haystack index:
                owner_projects_sq = base_owner_projects_sq.filter(id=owner_project_instance.id)
                if owner_projects_sq.count() == 0:
                    # continue till get to the first project found in haystack.
                    # Note: all projects should be found in haystack always, so this would never happen.
                    continue
                old_owner_name = owner_projects_sq[0].owner_name
                # if indexed owner_name is different from the current user name:
                if old_owner_name != instance.name:
                    using_backends = self.connection_router.for_write(instance=owner_project_instance)
                    for using in using_backends:
                        try:
                            index = self.connections[using].get_unified_index().get_index(Project)
                            if hasattr(index, 'update_owner_projects'):
                                # update the owner_name of the owner projects:
                                index.update_owner_projects(owner=instance, using=using)
                        except NotHandled:
                            # TODO: Maybe log it or let the exception bubble?
                            pass
                break

        else:
            super(IgniteSignalProcessor, self).handle_save(sender, instance, **kwargs)

    def handle_delete(self, sender, instance, **kwargs):
        if sender not in self.index_models:
            return

        super(IgniteSignalProcessor, self).handle_delete(sender, instance, **kwargs)
