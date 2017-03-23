Wagtail PostgreSQL full text search backend
===========================================

.. image:: http://img.shields.io/travis/leukeleu/wagtail-pg-search-backend/master.svg
   :target: https://travis-ci.org/leukeleu/wagtail-pg-search-backend

A PostgreSQL full text search backend for Wagtail CMS.


Installation
------------

PostgreSQL fulll text search requires PostgreSQL >= 9.4,
Django >= 1.10 and Wagtail >= 1.8.

To start using PostgreSQL full text search you'll need to do a
little bit of configuration.

Add the following to the project's settings::

    INSTALLED_APPS = [
        ...
        'wagtail_pgsearchbackend'
        ...
    ]

    WAGTAILSEARCH_BACKENDS = {
        'default': {
            'BACKEND': 'wagtail_pgsearchbackend.backend',
        }
    }

Then run migrations to add the required database tables, e.g.::

    ./manage.py migrate


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

To run the unittest against all supported versions of Python and Wagtail run::

    tox

The tox run will also create a coverage report combining the results
of all runs. This report is located in ``htmlcov/index.html``.
