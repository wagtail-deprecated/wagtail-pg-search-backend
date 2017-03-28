import re

from django.apps import apps
from django.db import connections
from wagtail.wagtailsearch.index import Indexed, RelatedFields, SearchField

try:
    # Only use the GPLv2 licensed unidecode if it's installed.
    from unidecode import unidecode
except ImportError:
    def unidecode(value):
        return value


def get_postgresql_connections():
    return [connection for connection in connections.all()
            if connection.vendor == 'postgresql']


def keyword_split(keywords):
    """
    Return all the keywords in a keyword string.

    Keeps keywords surrounded by quotes together, removing the surrounding quotes:

    >>> keyword_split('Hello I\\'m looking for "something special"')
    ['Hello', "I'm", 'looking', 'for', 'something special']

    Nested quoted strings are returned as is:

    >>> keyword_split("He said \\"I'm looking for 'something special'\\" so I've given him the 'special item'")
    ['He', 'said', "I'm looking for 'something special'", 'so', "I've", 'given', 'him', 'the', 'special item']

    """
    matches = re.findall(r'"([^"]+)"|\'([^\']+)\'|(\S+)', keywords)
    return [match[0] or match[1] or match[2] for match in matches]


def get_ancestor_models(model):
    """
    This returns all ancestors of a model, including the model itself.
    """
    models = [model]
    models.extend(model._meta.parents)
    return models


def get_search_fields(search_fields):
    for search_field in search_fields:
        if isinstance(search_field, SearchField):
            yield search_field
        elif isinstance(search_field, RelatedFields):
            for sub_field in get_search_fields(search_field.fields):
                yield sub_field


WEIGHTS = 'ABCD'
WEIGHTS_COUNT = len(WEIGHTS)
# These are filled when apps are ready.
BOOSTS_WEIGHTS = []
WEIGHTS_VALUES = []


def determine_boosts_weights():
    boosts = set()
    for model in apps.get_models():
        if issubclass(model, Indexed):
            for search_field in get_search_fields(model.get_search_fields()):
                boost = search_field.boost
                boosts.add(0 if boost is None else boost)
    if len(boosts) <= WEIGHTS_COUNT:
        return zip(reversed(sorted(boosts)), WEIGHTS)
    min_boost = min(boosts)
    max_boost = max(boosts)
    boost_step = (max_boost - min_boost) / WEIGHTS_COUNT
    return [(min_boost + (i * boost_step), weight)
            for i, weight in zip(range(WEIGHTS_COUNT), WEIGHTS)]


def get_weight(boost):
    if boost is None:
        boost = 0
    for max_boost, weight in BOOSTS_WEIGHTS:
        if boost >= max_boost:
            return weight
