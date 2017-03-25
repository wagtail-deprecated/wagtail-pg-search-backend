# coding: utf-8

from __future__ import unicode_literals

import operator
from functools import partial, reduce

from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.search import (
    SearchQuery, SearchRank, SearchVector)
from django.db import DEFAULT_DB_ALIAS, connections, transaction
from django.db.models import F, Manager, Q, TextField, Value
from django.db.models.functions import Cast
from django.utils.encoding import force_text, python_2_unicode_compatible
from django.utils.six import string_types
from wagtail.wagtailsearch.backends.base import (
    BaseSearchBackend, BaseSearchQuery, BaseSearchResults)
from wagtail.wagtailsearch.index import RelatedFields, SearchField

from .models import IndexEntry
from .utils import (
    WEIGHTS_VALUES, get_ancestor_models, get_weight, keyword_split, unidecode)

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
        self.search_fields = self.model.get_search_fields()

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
        return self.backend.params.get('SEARCH_CONFIG',
                                       DEFAULT_SEARCH_CONFIGURATION)

    def prepare_value(self, value):
        if isinstance(value, string_types):
            return value
        if isinstance(value, list):
            return ', '.join(self.prepare_value(item) for item in value)
        if isinstance(value, dict):
            return ', '.join(self.prepare_value(item)
                             for item in value.values())
        return force_text(value)

    def prepare_field(self, obj, field):
        if isinstance(field, SearchField):
            yield (unidecode(self.prepare_value(field.get_value(obj))),
                   get_weight(field.boost))
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
            for sub_obj in sub_objs:
                for sub_field in field.fields:
                    for value in self.prepare_field(sub_obj, sub_field):
                        yield value

    def prepare_body(self, obj):
        return [(value, boost) for field in self.search_fields
                for value, boost in self.prepare_field(obj, field)]

    def add_item(self, obj):
        self.add_items(self.model, [obj])

    def add_items_upsert(self, connection, content_types, objs, config):
        vectors_sql = []
        data_params = []
        sql_template = "setweight(to_tsvector('%s', %%s), %%s)" % config
        for content_type in content_types:
            for obj in objs:
                vectors_sql.append('||'.join(sql_template for _ in obj._body_))
                data_params.extend((content_type.pk, obj._object_id))
                data_params.extend([v for t in obj._body_ for v in t])
        data_sql = ', '.join(['(%%s, %%s, %s)' % s for s in vectors_sql])
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO %s(content_type_id, object_id, body_search)
                (VALUES %s)
                ON CONFLICT (content_type_id, object_id)
                DO UPDATE SET body_search = EXCLUDED.body_search
                """ % (IndexEntry._meta.db_table, data_sql), data_params)

    def add_items_update_then_create(self, content_types, objs, config):
        ids_and_objs = {}
        for obj in objs:
            obj._search_vector = ADD([
                SearchVector(Value(text), weight=weight, config=config)
                for text, weight in obj._body_])
            ids_and_objs[obj._object_id] = obj
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
            obj._body_ = self.prepare_body(obj)
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
    def __init__(self, *args, **kwargs):
        super(PostgresSearchQuery, self).__init__(*args, **kwargs)
        self.search_fields = self.queryset.model.get_search_fields()

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

    def get_boost(self, field_name):
        # TODO: Handle related fields.
        for field in self.search_fields:
            if field.field_name == field_name:
                return field.boost

    def get_in_fields_queryset(self, queryset, search_query):
        return (
            queryset.annotate(
                _search_=ADD(
                    SearchVector(field, config=search_query.config,
                                 weight=get_weight(self.get_boost(field)))
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
        pks = index_entries.rank(search_query).pks()
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
                .annotate(_rank_=SearchRank(F('_search_'), search_query,
                                            weights=WEIGHTS_VALUES))
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


class PostgresSearchRebuilder:
    def __init__(self, index):
        self.index = index

    def start(self):
        self.index.delete_stale_entries()
        return self.index

    def finish(self):
        pass


class PostgresSearchAtomicRebuilder(PostgresSearchRebuilder):
    def __init__(self, index):
        super(PostgresSearchAtomicRebuilder, self).__init__(index)
        # TODO: Get the DB alias another way.
        db_alias = DEFAULT_DB_ALIAS
        self.transaction = transaction.atomic(using=db_alias)
        self.transaction_opened = False

    def start(self):
        self.transaction.__enter__()
        self.transaction_opened = True
        return super(PostgresSearchAtomicRebuilder, self).start()

    def finish(self):
        self.transaction.__exit__(None, None, None)
        self.transaction_opened = False

    def __del__(self):
        # TODO: Implement a cleaner way to close the connection on failure.
        if self.transaction_opened:
            self.transaction.needs_rollback = True
            self.finish()


# FIXME: Take the database name into account.


class PostgresSearchBackend(BaseSearchBackend):
    query_class = PostgresSearchQuery
    results_class = PostgresSearchResult
    rebuilder_class = PostgresSearchRebuilder
    atomic_rebuilder_class = PostgresSearchAtomicRebuilder

    def __init__(self, params):
        super(PostgresSearchBackend, self).__init__(params)
        self.params = params
        if params.get('ATOMIC_REBUILD', False):
            self.rebuilder_class = self.atomic_rebuilder_class

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
