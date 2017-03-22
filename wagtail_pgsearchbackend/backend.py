from __future__ import unicode_literals

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.search import SearchQuery, SearchVector
from django.db import connections, DEFAULT_DB_ALIAS
from django.db.models import Q, Value
from django.utils.translation import get_language
from wagtail.wagtailsearch.backends.base import (
    BaseSearchQuery, BaseSearchResults, BaseSearchBackend,
)
from wagtail.wagtailsearch.index import SearchField

from .models import IndexEntry


DEFAULT_SEARCH_CONFIGURATION = 'simple'


def get_db_alias(queryset):
    return queryset._db or DEFAULT_DB_ALIAS


def get_sql(queryset):
    return queryset.query.get_compiler(get_db_alias(queryset)).as_sql()


class Index:
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

    def prepare_body(self, obj, boost=False):
        body = []
        for field in obj.get_search_fields():
            if isinstance(field, SearchField):
                value = field.get_value(obj)
                if value:
                    if boost and field.boost is not None:
                        # TODO: Handle float boost.
                        for i in range(round(field.boost)):
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
                        Value(self.prepare_body(obj, boost=True)),
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
        return Q(**{field.get_attname(self.queryset.model)
                    + '__' + lookup: value})

    def _connect_filters(self, filters, connector, negated):
        if connector == 'AND':
            q = Q(*filters)
        elif connector == 'OR':
            q = filters[0]
            for filter in filters[1:]:
                q |= filter
        else:
            return

        return ~q if negated else q


class PostgresSearchResult(BaseSearchResults):
    def get_pks(self):
        queryset = self.query.queryset.filter(
            self.query._get_filters_from_queryset())

        index_entries = IndexEntry.objects.for_queryset(queryset)

        if self.query.query_string is not None:
            index_entries = index_entries.filter(
                body_search=SearchQuery(
                    self.query.query_string,
                    config=(self.backend.get_index_for_model(queryset.model)
                            .get_config_for())))
            # TODO: Add ranking.

        return index_entries.pks()[self.start:self.stop]

    def _do_search(self):
        pks = self.get_pks()
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
