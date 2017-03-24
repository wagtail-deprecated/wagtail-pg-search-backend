Wagtail PostgreSQL full text search backend
===========================================

.. image:: http://img.shields.io/travis/leukeleu/wagtail-pg-search-backend/master.svg
   :target: https://travis-ci.org/leukeleu/wagtail-pg-search-backend

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

* ```ATOMIC_REBUILD`_`` behaviour is not implemented.

* ``SearchField.partial_match`` behaviour is not implemented.

* ``SearchField.boost`` does not handle floats. Boost values are rounded.

* ``SearchField.es_extra`` is not handled because it is specific
  to ElasticSearch.

* ``SearchQuerySet.search`` limiting search to specific field(s) is only
  supported for database fields, not methods.

.. _ATOMIC_REBUILD: http://docs.wagtail.io/en/v1.9/topics/search/backends.html#atomic-rebuild


Performance
~~~~~~~~~~~

The PostgreSQL search backend has been tried and tested on a few small
to medium sized website and its performance compares favorably to that
of ElasticSearch.

Some noticeable speed improvements are in place when using PostgreSQL >= 9.5.


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
