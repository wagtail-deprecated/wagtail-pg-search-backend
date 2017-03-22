from __future__ import unicode_literals

from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.search import SearchQuery
from django.db.models import Q, TextField
from django.db.models.functions import Cast
from wagtail.wagtailsearch.backends.base import (
    BaseSearchQuery, BaseSearchResults, BaseSearchBackend)
from wagtail.wagtailsearch.index import SearchField

from .models import IndexEntry


class Index:
    def __init__(self, model):
        self.models = [model]
        self.name = model._meta.label

    def add_model(self, model):
        self.models.append(model)

    def get_config_for(self, language):
        # FIXME: Change this.
        return language

    def prepare_body(self, obj):
        body = []
        for field in obj.get_search_fields():
            if isinstance(field, SearchField):
                value = field.get_value(obj)
                if value:
                    # TODO: Handle float boost.
                    for i in range(round(field.boost)):
                        body.append(value)
                    # TODO: Handle RelatedFields.
                    # TODO: Handle extra fields.
        return ' '.join(body)

    def add_item(self, obj):
        language = getattr(obj, 'get_language', '')
        if callable(language):
            language = language()

        config = self.get_config_for(language)
        body = self.prepare_body(obj)
        for model in obj._meta.parents:
            IndexEntry.objects.update_or_create(
                config=config,
                content_type=ContentType.objects.get_for_model(model),
                object_id=str(obj.pk),
                defaults=dict(
                    title=str(obj),
                    body=body,
                    body_search=body,
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

    def get_pks(self):
        queryset = self.queryset.filter(self._get_filters_from_queryset())

        index_entries = IndexEntry.objects.for_queryset(queryset)

        if self.query_string is not None:
            index_entries = index_entries.filter(
                body_search=SearchQuery(self.query_string))
            # TODO: Add ranking.

        return index_entries.values_list('object_id', flat=True)


class PostgresSearchResult(BaseSearchResults):
    def get_pks(self):
        return self.query.get_pks()[self.start:self.stop]

    def _do_search(self):
        pks = self.get_pks()
        results = (self.query.queryset
                   .annotate(pk_text=Cast('pk', TextField()))
                   .filter(pk_text__in=pks))
        results = {str(result.pk): result for result in results}
        return [results[pk] for pk in pks if pk in results]

    def _do_count(self):
        return self.get_pks().count()


class PostgresSearchRebuilder(object):
    def __init__(self, index):
        self.index = index

    def start(self):
        return self.index

    def finish(self):
        pass


# FIXME: Take the database name into account.


class PostgresSearchBackend(BaseSearchBackend):
    query_class = PostgresSearchQuery
    results_class = PostgresSearchResult
    rebuilder_class = PostgresSearchRebuilder

    def get_index_for_model(self, model):
        return Index(model)

    def reset_index(self):
        IndexEntry.objects.all().delete()

    def add_type(self, model):
        pass  # Not needed.

    def refresh_index(self):
        pass  # Not needed.

    def add(self, obj):
        Index(obj._meta.model).add_item(obj)

    def add_bulk(self, model, obj_list):
        Index(model).add_items(model, obj_list)

    def delete(self, obj):
        IndexEntry.objects.for_object(obj).delete()


SearchBackend = PostgresSearchBackend
