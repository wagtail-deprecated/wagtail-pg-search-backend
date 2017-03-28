Wagtail PostgreSQL full text search backend
===========================================

.. image:: http://img.shields.io/travis/wagtail/wagtail-pg-search-backend/master.svg
   :target: https://travis-ci.org/wagtail/wagtail-pg-search-backend

A PostgreSQL full text search backend for Wagtail CMS.


Installation
------------

PostgreSQL full text search in Wagtail requires PostgreSQL >= 9.2
(noticable speed improvements are in place for PostgreSQL >= 9.5),
Django >= 1.10 and Wagtail >= 1.8.

First, install the module using::

    pip install wagtail-pg-search-backend

Then you'll need to do a little bit of configuration.

Add the following to the project settings::

    INSTALLED_APPS = [
        ...
        'wagtail_pgsearchbackend'
        ...
    ]

    WAGTAILSEARCH_BACKENDS = {
        'default': {
            'BACKEND': 'wagtail_pgsearchbackend.backend',
            'SEARCH_CONFIG': 'english'
        }
    }

Then run migrations to add the required database table::

    ./manage.py migrate wagtail_pgsearchbackend


Configuration
-------------

The ``SEARCH_CONFIG`` key takes a text search configuration name.
This controls the stemming, stopwords etc. used when searching and
indexing the database. To get a list of the available config names
use this query::

    SELECT cfgname FROM pg_catalog.pg_ts_config


Usage
-----

This backend implements the required methods to be compatible
with most features mentioned in the the
`Wagtail search docs`_.

.. _Wagtail search docs: http://docs.wagtail.io/en/v1.9/topics/search/backends.html


Known limitations
~~~~~~~~~~~~~~~~~

* Multiple databases are not handled properly.

* ``SearchField.partial_match`` behaviour is not implemented.

* Due to a PostgreSQL limitation, ``SearchField.boost`` is only partially
  respected. It is changed so that there can only be 4 different boosts.
  If you define 4 or less different boosts,
  everything will be perfectly accurate.
  However, your search will be a little less accurate if you define more than
  4 different boosts. That being said, it will work and be roughly the same.

* ``SearchField.es_extra`` is not handled because it is specific
  to ElasticSearch.

* Using ``SearchQuerySet.search`` while limiting to specific field(s) is only
  supported for database fields, not methods.


Performance
~~~~~~~~~~~

The PostgreSQL search backend has been tried and tested on a few small
to medium sized website and its performance compares favorably to that
of ElasticSearch.

Some noticeable speed improvements are in place when using PostgreSQL >= 9.5.


Features to add
---------------

These features would awesome to have once this project is merged with Wagtail:

- Per-object boosting
- Faceting
- Autocomplete (maybe it should replace partial search?)
- Spelling suggestions


Development
-----------

Install the package and dev requirements::

    pip install -e . -r requirements-dev.txt


Creating migrations
~~~~~~~~~~~~~~~~~~~

First create a database::

    createdb -Upostgres wagtail_pgsearchbackend

Then call makemigrations using the test settings::

    django-admin makemigrations --settings=tests.settings


Testing
~~~~~~~

To run the unittests for the current environment's Python version
and Wagtail run::

    make unittests

To check the code for style errors run::

    make flaketest

To combine these tasks run::

    make

To run the unittest against all supported versions of Python and
Wagtail run::

    tox

The tox run will also create a coverage report combining the results
of all runs. This report is located in ``htmlcov/index.html``.

To run individual tests by name use the ``runtests.py`` script and give
the dotted path the the test module(s), class(es) or method(s) that you
want to test e.g.::

    ./runtests.py tests.test_module.TestClass.test_method

