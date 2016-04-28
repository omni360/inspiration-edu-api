from haystack.query import SearchQuerySet, SQ
from api.models import Project, Lesson, IgniteUser


def get_searched_projects_ids(search_query, filter_or=False, search_in_lesson=False):
    search_query_set = SearchQuerySet()
    search_query_set = search_query_set.models(Project)

    search_params = filter(None, search_query.split(' '))

    # If no search params, then return all:
    if not search_params:
        return search_query_set.all()

    sq_filter = None
    for param in search_params:
        if param.startswith('-'):
            search_query_set = search_query_set.exclude(content=param[1:])
        else:
            _sq_filter = SQ(content__startswith=param)
            if sq_filter:
                if filter_or:
                    sq_filter |= _sq_filter
                else:
                    sq_filter &= _sq_filter
            else:
                sq_filter = _sq_filter

    # If search_in_lesson, then include the results from lesson index:
    if search_in_lesson:
        lesson_projects_ids = get_projects_ids_searched_by_lesson_titles(search_query)
        _sq_filter = SQ(id__in=lesson_projects_ids)
        if sq_filter:
            if filter_or:
                sq_filter |= _sq_filter
            else:
                sq_filter &= _sq_filter
        else:
            sq_filter = _sq_filter

    # Since sq.exclude.exclude.filter_or returns wrong data, we bypass it with a single .filter in the end:
    if sq_filter is not None:
        search_query_set = search_query_set.filter(sq_filter)

    return search_query_set.values_list('pk', flat=True)


def get_projects_ids_searched_by_lesson_titles(search_query, filter_or=False):
    search_query_set = SearchQuerySet()
    search_query_set = search_query_set.models(Lesson)

    search_params = filter(None, search_query.split(' '))

    # If no search params, then return all:
    if not search_params:
        return set(search_query_set.values_list('project_id', flat=True))

    sq_filter = None
    for param in search_params:
        if param.startswith('-'):
            search_query_set = search_query_set.exclude(content=param[1:])
        else:
            _sq_filter = SQ(content__startswith=param)
            if sq_filter:
                if filter_or:
                    sq_filter |= _sq_filter
                else:
                    sq_filter &= _sq_filter
            else:
                sq_filter = _sq_filter

    # Since sq.exclude.exclude.filter_or returns wrong data, we bypass it with a single .filter in the end:
    if sq_filter is not None:
        search_query_set = search_query_set.filter(sq_filter)

    return set(search_query_set.values_list('project_id', flat=True))


def get_projects_ids_searched_by_title_tags_author(search_query, filter_or=False):
    search_query_set = SearchQuerySet()
    search_query_set = search_query_set.models(Project)

    search_params = filter(None, search_query.split(' '))

    # If no search params, then return all:
    if not search_params:
        return search_query_set.all()

    sq_filter = None
    for param in search_params:
        if param.startswith('-'):
            param = param[1:]  # remove - sign
            search_query_set = search_query_set.exclude(title=param)
            search_query_set = search_query_set.exclude(tags=param)
            search_query_set = search_query_set.exclude(owner_name=param)
        else:
            _sq_filter = SQ(title=param)
            _sq_filter |= SQ(tags=param)
            _sq_filter |= SQ(owner_name=param)
            if sq_filter:
                if filter_or:
                    sq_filter |= _sq_filter
                else:
                    sq_filter &= _sq_filter
            else:
                sq_filter = _sq_filter

    # Since sq.exclude.exclude.filter_or returns wrong data, we bypass it with a single .filter in the end:
    if sq_filter is not None:
        search_query_set = search_query_set.filter(sq_filter)

    return search_query_set.values_list('pk', flat=True)


def get_projects_ids_searched_by_exact_tags(search_query_list, filter_or=False):
    search_query_set = SearchQuerySet()
    search_query_set = search_query_set.models(Project)

    search_query_list = search_query_list if isinstance(search_query_list, list) else [search_query_list]

    for search_query in search_query_list:
        filter_callback = search_query_set.filter_or if filter_or else search_query_set.filter
        search_query_set = filter_callback(tags__exact=search_query)

    return search_query_set.values_list('pk', flat=True)
