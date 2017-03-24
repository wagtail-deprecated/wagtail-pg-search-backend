# coding: utf-8

from __future__ import unicode_literals

import operator
from functools import partial, reduce

import six
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.search import (
    SearchQuery, SearchRank, SearchVector)
from django.db import DEFAULT_DB_ALIAS, connections
from django.db.models import F, Manager, Q, TextField, Value
from django.db.models.functions import Cast
from django.utils.encoding import force_text, python_2_unicode_compatible
from django.utils.html import strip_tags
from wagtail.wagtailsearch.backends.base import (
    BaseSearchBackend, BaseSearchQuery, BaseSearchResults)
from wagtail.wagtailsearch.index import RelatedFields, SearchField

from .models import IndexEntry
from .utils import get_ancestor_models, keyword_split, unidecode

# TODO: Add autocomplete.

DEFAULT_SEARCH_CONFIGURATION = 'simple'

# Reduce any iterable to a single value using a logical OR e.g. (a | b | ...)
OR = partial(reduce, operator.or_)
# Reduce any iterable to a single value using a logical AND e.g. (a & b & ...)
AND = partial(reduce, operator.and_)
# Reduce any iterable to a single value using an addition
ADD = partial(reduce, operator.add)


def get_db_alias(queryset):
    return queryset._db or DEFAULT_DB_ALIAS


def get_sql(queryset):
    return queryset.query.get_compiler(get_db_alias(queryset)).as_sql()


@python_2_unicode_compatible
class Index(object):
    def __init__(self, backend, model):
        self.backend = backend
        self.model = model
        self.name = model._meta.label

    def add_model(self, model):
        pass

    def refresh(self):
        pass

    def delete_stale_entries(self):
        qs1 = IndexEntry.objects.for_model(self.model).values('object_id')
        # The empty `order_by` removes the order for performance’s sake.
        qs2 = self.model.objects.order_by().annotate(
            pk_text=Cast('pk', TextField())).values('pk_text')
        sql1, params1 = get_sql(qs1)
        sql2, params2 = get_sql(qs2)
        pks_sql = '(%s) EXCEPT (%s)' % (sql1, sql2)
        params = params1 + params2
        with connections[get_db_alias(qs1)].cursor() as cursor:
            cursor.execute('SELECT EXISTS (%s);' % pks_sql, params)
            has_stale_entries = cursor.fetchone()[0]
            if not has_stale_entries:
                return
            cursor.execute('DELETE FROM %s WHERE object_id IN (%s);'
                           % (IndexEntry._meta.db_table, pks_sql), params)

    def get_config(self):
        return self.backend.params.get(
            'SEARCH_CONFIG', DEFAULT_SEARCH_CONFIGURATION)

    def prepare_value(self, value):
        if isinstance(value, six.string_types):
            if '</' in value:
                return strip_tags(value)
            return value
        if isinstance(value, list):
            return ', '.join(self.prepare_value(item) for item in value)
        if isinstance(value, dict):
            return ', '.join(self.prepare_value(item)
                             for item in value.values())
        return force_text(value)

    def prepare_field(self, obj, field):
        if isinstance(field, SearchField):
            value = self.prepare_value(field.get_value(obj))
            if field.boost is not None:
                # TODO: Handle float boost.
                boost = int(round(field.boost)) or 1
                for _ in range(boost):
                    yield value
            yield value
        elif isinstance(field, RelatedFields):
            sub_obj = getattr(obj, field.field_name)
            if sub_obj is None:
                return
            if callable(sub_obj):
                sub_obj = sub_obj()
            if isinstance(sub_obj, Manager):
                sub_objs = sub_obj.all()
            else:
                sub_objs = [sub_obj]
            values = []
            for sub_obj in sub_objs:
                for sub_field in field.fields:
                    for value in self.prepare_field(sub_obj, sub_field):
                        yield value
                        values.append(value)

    def prepare_body(self, obj):
        return ' '.join(filter(bool, [
            value for field in obj.get_search_fields()
            for value in self.prepare_field(obj, field)]))

    def add_item(self, obj):
        self.add_items(obj._meta.model, [obj])

    def add_items_upsert(self, connection, content_types, objs, config):
        data = []
        for content_type in content_types:
            for obj in objs:
                data.extend(
                    (content_type.pk, obj._object_id, obj._search_vector))
        row_template = "(%%s, %%s, to_tsvector('%s', %%s))" % config
        data_template = ', '.join([row_template
                                   for _ in range(len(data) // 3)])
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO %s(content_type_id, object_id, body_search)
                (VALUES %s)
                ON CONFLICT (content_type_id, object_id)
                DO UPDATE SET body_search = EXCLUDED.body_search
                """ % (IndexEntry._meta.db_table, data_template), data)

    def add_items_update_then_create(self, content_types, objs, config):
        for obj in objs:
            obj._search_vector = SearchVector(Value(obj._search_vector),
                                              config=config)
        ids_and_objs = {obj._object_id: obj for obj in objs}
        indexed_ids = frozenset(
            IndexEntry.objects.filter(content_type__in=content_types,
                                      object_id__in=ids_and_objs)
            .values_list('object_id', flat=True))
        for indexed_id in indexed_ids:
            obj = ids_and_objs[indexed_id]
            IndexEntry.objects.filter(content_type__in=content_types,
                                      object_id=obj._object_id) \
                .update(body_search=obj._search_vector)
        to_be_created = []
        for object_id in ids_and_objs:
            if object_id not in indexed_ids:
                for content_type in content_types:
                    to_be_created.append(IndexEntry(
                        content_type=content_type,
                        object_id=object_id,
                        body_search=ids_and_objs[object_id]._search_vector,
                    ))
        IndexEntry.objects.bulk_create(to_be_created)

    def add_items(self, model, objs):
        content_types = (ContentType.objects
                         .get_for_models(*get_ancestor_models(model)).values())
        config = self.get_config()
        for obj in objs:
            obj._object_id = force_text(obj.pk)
            obj._search_vector = unidecode(self.prepare_body(obj))
        # TODO: Get the DB alias another way.
        db_alias = DEFAULT_DB_ALIAS
        connection = connections[db_alias]
        if connection.pg_version >= 90500:  # PostgreSQL >= 9.5
            self.add_items_upsert(connection, content_types, objs, config)
        else:
            self.add_items_update_then_create(content_types, objs, config)

    def __str__(self):
        return self.name


class PostgresSearchQuery(BaseSearchQuery):
    def _process_lookup(self, field, lookup, value):
        return Q(
            **{field.get_attname(self.queryset.model) + '__' + lookup: value})

    def _connect_filters(self, filters, connector, negated):
        if not filters:
            return Q()
        combine = AND if connector == 'AND' else OR
        q = combine(filters)
        return ~q if negated else q

    def get_search_query(self, config):
        combine = AND if self.operator == 'and' else OR
        search_terms = keyword_split(unidecode(self.query_string))
        return combine(SearchQuery(q, config=config) for q in search_terms)

    def get_base_queryset(self):
        queryset = self.queryset.filter(self._get_filters_from_queryset())
        # Removes order for performance’s sake.
        return queryset.order_by()

    def get_in_index_queryset(self, queryset, search_query):
        return (IndexEntry.objects.for_queryset(queryset)
                .filter(body_search=search_query))

    def get_in_fields_queryset(self, queryset, search_query):
        # TODO: Take boost into account.
        return (queryset.annotate(_search_=ADD(SearchVector(field)
                                               for field in self.fields))
                .filter(_search_=search_query))

    def search_count(self, config):
        queryset = self.get_base_queryset()
        search_query = self.get_search_query(config=config)
        queryset = (self.get_in_index_queryset(queryset, search_query)
                    if self.fields is None
                    else self.get_in_fields_queryset(queryset, search_query))
        return queryset.count()

    def search_in_index(self, queryset, search_query, start, stop):
        index_entries = self.get_in_index_queryset(queryset, search_query)
        index_entries = index_entries.annotate(
            rank=SearchRank(F('body_search'), search_query)
        ).order_by('-rank')
        pks = index_entries.pks()
        pks_sql, params = get_sql(pks)
        meta = queryset.model._meta
        return queryset.model.objects.raw(
            'SELECT * FROM (%s) AS pks(pk) '
            'INNER JOIN %s ON %s = pks.pk '
            'OFFSET %%s LIMIT %%s'
            % (pks_sql, meta.db_table, meta.pk.get_attname_column()[1]),
            params + (start, None if stop is None else stop - start))

    def search_in_fields(self, queryset, search_query, start, stop):
        return (self.get_in_fields_queryset(queryset, search_query)
                .annotate(_rank_=SearchRank(F('_search_'), search_query))
                .order_by('-_rank_'))[start:stop]

    def search(self, config, start, stop):
        queryset = self.get_base_queryset()
        if self.query_string is None:
            return queryset[start:stop]
        search_query = self.get_search_query(config=config)
        if self.fields is None:
            return self.search_in_index(queryset, search_query, start, stop)
        return self.search_in_fields(queryset, search_query, start, stop)


class PostgresSearchResult(BaseSearchResults):
    def get_config(self):
        return self.backend.get_index_for_model(
            self.query.queryset.model).get_config()

    def _do_search(self):
        return list(self.query.search(self.get_config(),
                                      self.start, self.stop))

    def _do_count(self):
        return self.query.search_count(self.get_config())


class PostgresSearchRebuilder(object):
    def __init__(self, index):
        self.index = index

    def start(self):
        self.index.delete_stale_entries()
        return self.index

    def finish(self):
        pass


# FIXME: Take the database name into account.


class PostgresSearchBackend(BaseSearchBackend):
    query_class = PostgresSearchQuery
    results_class = PostgresSearchResult
    rebuilder_class = PostgresSearchRebuilder

    def __init__(self, params):
        super(PostgresSearchBackend, self).__init__(params)
        self.params = params

    def get_index_for_model(self, model):
        return Index(self, model)

    def reset_index(self):
        IndexEntry.objects.all().delete()

    def add_type(self, model):
        pass  # Not needed.

    def refresh_index(self):
        pass  # Not needed.

    def add(self, obj):
        self.get_index_for_model(obj._meta.model).add_item(obj)

    def add_bulk(self, model, obj_list):
        self.get_index_for_model(model).add_items(model, obj_list)

    def delete(self, obj):
        IndexEntry.objects.for_object(obj).delete()


SearchBackend = PostgresSearchBackend
