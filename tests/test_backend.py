import unittest

from django.test import TestCase

from wagtail.wagtailsearch.tests.test_backends import BackendTests


class TestPgSearchBackend(BackendTests, TestCase):
    backend_path = 'wagtail_pgsearchbackend.backend'

    def reset_index(self):
        self.backend.reset_index()
