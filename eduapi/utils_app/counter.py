import types
from django.db import models


class RelatedCounterError(Exception):
    pass


class ExtendQuerySetWithSubRelated(object):
    """
    Builder class from QuerySet that returns instance of QuerySetWithSubRelated.
    """

    class QuerySetWithSubRelated(models.QuerySet):
        """
        Queryset with annotate_related() method that automatically creates related subquery for a related field
        in SELECT clause, and aggregates data in that subquery.
        Also has add_counter() method that automatically adds a counter field for related field (private case of annotate_related).

        IMPORTANT: Try not to use this type of queryset inside of filters, since it is hard-coded to use db_table names
            without aliases. Using this queryset inside filters will likely fail to build query since inside filters
            the tables are usually aliased.
            It is safe to use on Prefetch querysets.

        NOTE: This queryset might fail to build when connecting to aliased tables.
        """
        def annotate_related(self, annotate_name, annotate_agg, field_name, related_queryset=None, default_agg_value=0):
            '''
            Annotates the queryset with a related subquery.

            :param annotate_name: The annotated field name in SELECT.
            :param annotate_agg: The annotate aggregation (e.g Count, Avg, Sum, etc).
            :param field_name: The related field name to start subquery from.
            :param related_queryset: The related queryset to use (defaults to related field model.objects.all()).
            :param default_agg_value: Default value to return if subquery matches no rows (instead of None) (defaults to 0).
            :return: QuerySetWithSubRelated.
            '''

            #try get the field:
            try:
                related_field, _model, _direct, _m2m = self.model._meta.get_field_by_name(field_name)
            except models.FieldDoesNotExist:
                raise

            #make related queryset, calculate subquery params:
            if isinstance(related_field, models.ForeignKey):
                related_queryset = related_queryset if related_queryset is not None else related_field.rel.to.objects.all()
                if related_field.rel.to != related_queryset.model:
                    raise RelatedCounterError('Related field model does not match related queryset model')
                subquery_params = {
                    'par_table': related_field.model._meta.db_table,
                    'rel_table': related_field.rel.to._meta.db_table,
                    'par_field': related_field.attname,
                    'rel_field': related_field.rel.field_name,
                }
            elif not _direct:
                related_queryset = related_queryset if related_queryset is not None else related_field.model.objects.all()
                if related_field.model != related_queryset.model:
                    raise RelatedCounterError('Related field model does not match related queryset model')
                subquery_params = {
                    'par_table': related_field.parent_model._meta.db_table,
                    'rel_table': related_field.model._meta.db_table,
                    'par_field': related_field.field.rel.field_name,
                    'rel_field': related_field.field.attname,
                }
            else:
                raise RelatedCounterError('Not related field')

            #make the related annotated queryset (group and order only by the same related field, and select the aggregated value):
            #Note: if not ordered by related field and model has its own different order, then it will join the parent table into the subquery, and query will fail.
            related_annotated_queryset = related_queryset.extra(
                where=[
                    '"%(rel_table)s"."%(rel_field)s"="%(par_table)s"."%(par_field)s"' % subquery_params
                ]
            )\
                .values(subquery_params['rel_field'])\
                .order_by(subquery_params['rel_field'])\
                .annotate(agg_value=annotate_agg)\
                .values('agg_value')

            query_sql, query_params = related_annotated_queryset.query.sql_with_params()
            return self.extra(
                    select={annotate_name: 'COALESCE((' + query_sql + '), %s)'},
                    select_params=query_params + (default_agg_value,),
            )

        def add_counter(self, annotate_name, field_name, related_queryset=None, count_on_field='pk'):
            '''
            Annotates the queryset with a counter on a related field.

            :param annotate_name: The annotated field name in SELECT.
            :param field_name: The related field name to start subquery from.
            :param related_queryset: The related queryset to use (defaults to related field model.objects.all()).
            :param count_on_field: The field to count in the related subquery (defaults to 'pk').
            :return: QuerySetWithSubRelated.
            '''
            return self.annotate_related(annotate_name, models.Count(count_on_field), field_name, related_queryset)

    def __new__(cls, queryset, *args, **kwargs):
        #if already with counter, then return the same queryset:
        if isinstance(queryset, cls.QuerySetWithSubRelated):
            return queryset

        #clone the queryset from QuerySetWithRelatedCounter:
        queryset_with_related_counter_class = type(queryset.__class__.__name__ + 'WithRelatedCounter', (cls.QuerySetWithSubRelated, queryset.__class__), {})
        return queryset._clone(klass=queryset_with_related_counter_class, setup=False)
