from __future__ import unicode_literals

from wagtail.wagtailsearch.backends.base import (
    BaseSearchQuery, BaseSearchResults, BaseSearchBackend)


class PgSearchQuery(BaseSearchQuery):
    pass


class PgSearchResult(BaseSearchResults):
    pass


class PgSearchRebuilder(object):
    pass


class PgSearchBackend(BaseSearchBackend):
    query_class = PgSearchQuery
    results_class = PgSearchResult
    rebuilder_class = PgSearchRebuilder


SearchBackend = PgSearchBackend
