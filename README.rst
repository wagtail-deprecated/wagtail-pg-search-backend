Wagtail PostgreSQL full text search backend
===========================================

A PostgreSQL full text search backend for Wagtail CMS.

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
