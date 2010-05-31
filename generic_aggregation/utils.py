from django.contrib.contenttypes.models import ContentType
from django.db import connection, models

def generic_annotate(queryset, gfk_field, aggregate_field, aggregator=models.Sum,
        generic_queryset=None, desc=True):
    ordering = desc and '-score' or 'score'
    content_type = ContentType.objects.get_for_model(queryset.model)
    
    qn = connection.ops.quote_name
    
    # collect the params we'll be using
    params = (
        aggregator.name, # the function that's doing the aggregation
        qn(aggregate_field), # the field containing the value to aggregate
        qn(gfk_field.model._meta.db_table), # table holding gfk'd item info
        qn(gfk_field.ct_field + '_id'), # the content_type field on the GFK
        content_type.pk, # the content_type id we need to match
        qn(gfk_field.fk_field), # the object_id field on the GFK
        qn(queryset.model._meta.db_table), # the table and pk from the main
        qn(queryset.model._meta.pk.name)   # part of the query
    )
    
    extra = """
        SELECT %s(%s) AS aggregate_score
        FROM %s
        WHERE
            %s=%s AND
            %s=%s.%s
    """ % params
    
    if generic_queryset is not None:
        inner_query, inner_query_params = generic_queryset.values_list('pk').query.as_sql()
        
        inner_params = (
            qn(generic_queryset.model._meta.db_table),
            qn(generic_queryset.model._meta.pk.name),
        )
        inner_start = ' AND %s.%s IN (' % inner_params
        inner_end = ')'
        extra = extra + inner_start + inner_query + inner_end
    else:
        inner_query_params = []

    queryset = queryset.extra(
        select={'score': extra},
        select_params=inner_query_params,
        order_by=[ordering]
    )
    
    return queryset


def generic_aggregate(queryset, gfk_field, aggregate_field, aggregator=models.Sum,
        generic_queryset=None):
    content_type = ContentType.objects.get_for_model(queryset.model)
    
    queryset = queryset.values_list('pk') # just the pks
    query, query_params = queryset.query.as_nested_sql()
    
    qn = connection.ops.quote_name
    
    # collect the params we'll be using
    params = (
        aggregator.name, # the function that's doing the aggregation
        qn(aggregate_field), # the field containing the value to aggregate
        qn(gfk_field.model._meta.db_table), # table holding gfk'd item info
        qn(gfk_field.ct_field + '_id'), # the content_type field on the GFK
        content_type.pk, # the content_type id we need to match
        qn(gfk_field.fk_field), # the object_id field on the GFK
    )
    
    query_start = """
        SELECT %s(%s) AS aggregate_score
        FROM %s
        WHERE
            %s=%s AND
            %s IN (
                """ % params
    
    query_end = ")"
    
    if generic_queryset is not None:
        inner_query, inner_query_params = generic_queryset.values_list('pk').query.as_sql()
        
        query_params += inner_query_params
        
        inner_params = (
            qn(generic_queryset.model._meta.pk.name),
        )
        inner_start = ' AND %s IN (' % inner_params
        inner_end = ')'
        query_end = query_end + inner_start + inner_query + inner_end
    
    # pass in the inner_query unmodified as we will use the cursor to handle
    # quoting the inner parameters correctly
    query = query_start + query + query_end
    
    cursor = connection.cursor()
    cursor.execute(query, query_params)
    row = cursor.fetchone()

    return row[0]
