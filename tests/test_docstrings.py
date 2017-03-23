import doctest

from wagtail_pgsearchbackend import utils

DOCTEST_MODULES = {utils}


def load_tests(loader, tests, ignore):
    """
    Creates a ``DocTestSuite`` for each module named in ``DOCTEST_MODULES``
    and adds it to the test run.
    """
    for module in DOCTEST_MODULES:
        tests.addTests(doctest.DocTestSuite(module))
    return tests
