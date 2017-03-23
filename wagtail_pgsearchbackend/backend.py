from __future__ import unicode_literals

import operator
from functools import partial, reduce

import six

from bs4 import BeautifulSoup
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.search import (
    SearchQuery, SearchVector, SearchRank)
from django.db import DEFAULT_DB_ALIAS, connections
from django.db.models import Q, TextField, Value, F
from django.db.models.functions import Cast
from django.utils.encoding import force_text
from django.utils.translation import get_language
from unidecode import unidecode
from wagtail.wagtailsearch.backends.base import (
    BaseSearchBackend, BaseSearchQuery, BaseSearchResults)
from wagtail.wagtailsearch.index import SearchField

from . import utils
from .models import IndexEntry

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
        qs1 = IndexEntry.objects.for_model(self.model).pks()
        qs2 = self.model.objects.order_by().values('pk')
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

    def get_config_for(self, language=''):
        if not language:
            language = get_language() or settings.LANGUAGE_CODE
        return (self.backend.params.get('LANGUAGES_CONFIGS', {})
                .get(language, DEFAULT_SEARCH_CONFIGURATION))

    def prepare_value(self, value):
        if isinstance(value, six.string_types):
            if '</' in value:
                return BeautifulSoup(value, 'html5lib').text
            return value
        if isinstance(value, list):
            return ', '.join(self.prepare_value(item) for item in value)
        if isinstance(value, dict):
            return ', '.join(self.prepare_value(item)
                             for item in value.values())
        return force_text(value)

    def prepare_body(self, obj, boost=False):
        body = []
        for field in obj.get_search_fields():
            if isinstance(field, SearchField):
                value = self.prepare_value(field.get_value(obj))
                if value:
                    if boost and field.boost is not None:
                        # TODO: Handle float boost.
                        for i in range(int(round(field.boost)) or 1):
                            body.append(value)
                    else:
                        body.append(value)
                    # TODO: Handle RelatedFields.
                    # TODO: Handle extra fields.
        return ' '.join(body)

    def add_item(self, obj):
        language = getattr(obj, 'get_language', '')
        if callable(language):
            language = language()

        config = self.get_config_for(language)
        models = list(obj._meta.parents)
        models.append(obj._meta.model)
        for model in models:
            IndexEntry.objects.update_or_create(
                config=config,
                content_type=ContentType.objects.get_for_model(model),
                object_id=str(obj.pk),
                defaults=dict(
                    title=str(obj),
                    body=self.prepare_body(obj),
                    body_search=SearchVector(
                        Value(unidecode(self.prepare_body(obj, boost=True))),
                        config=config),
                ),
            )

    def add_items(self, model, objs):
        # TODO: Make something faster.
        for obj in objs:
            self.add_item(obj)

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
        search_terms = utils.keyword_split(unidecode(self.query_string))
        return combine(SearchQuery(q, config=config) for q in search_terms)

    def get_pks(self, config):
        queryset = self.queryset.filter(self._get_filters_from_queryset())

        index_entries = IndexEntry.objects.for_queryset(queryset)

        if self.query_string is not None:
            search_query = self.get_search_query(config=config)
            if self.fields is None:
                index_entries = index_entries.filter(body_search=search_query)
            else:
                original_pks = (
                    self.queryset
                    .annotate(search=ADD(SearchVector(field)
                                         for field in self.fields))
                    .filter(search=search_query)
                    .annotate(pk_text=Cast('pk', TextField()))
                    .values('pk_text'))
                index_entries = index_entries.filter(
                    object_id__in=original_pks)
            # TODO: Make another ranking system for searching specific fields.
            index_entries = index_entries.annotate(
                rank=SearchRank(F('body_search'), search_query)
            ).order_by('-rank')

        return index_entries.pks()


class PostgresSearchResult(BaseSearchResults):
    def _do_search(self):
        config = self.backend.get_index_for_model(
            self.query.queryset.model).get_config_for()
        pks = self.query.get_pks(config)[self.start:self.stop]
        results = {result.pk: result
                   for result in self.query.queryset.filter(pk__in=pks)}
        return [results[pk] for pk in pks if pk in results]

    def _do_count(self):
        return self.get_pks().count()


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
