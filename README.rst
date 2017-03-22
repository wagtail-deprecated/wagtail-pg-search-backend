Wagtail PostgreSQL full text search backend
===========================================

A PostgreSQL full text search backend for Wagtail CMS.


Installation
------------

To start using PostgreSQL full text search in your Wagtail
project you'll need to do a litte bit of configuration.

Add the following to the project's settings::

    INSTALLED_APPS += ['wagtail_pgsearchbackend']

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


Testing
~~~~~~~

To run the tests for the current environtment's Python version
and Wagtail run::

    python setup.py test


To test against all supported versions of Python and Wagtail run::

    tox

The tox run will also create a coverage report combining the results
of all runs. This report is located in ``htmlcov/index.html``.
