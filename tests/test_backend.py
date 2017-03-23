import unittest

from django.test import TestCase

from wagtail.wagtailsearch.tests.test_backends import BackendTests


class TestPgSearchBackend(BackendTests, TestCase):
    backend_path = 'wagtail_pgsearchbackend.backend'

    def reset_index(self):
        self.backend.reset_index()

    @unittest.expectedFailure
    def test_individual_field(self):
        """
        Searching in individual fields is not possible using
        an index model.

        """
        super(TestPgSearchBackend, self).test_individual_field()
