import unittest


class TestFail(unittest.TestCase):
    def test_fail(self):
        self.fail('Failure is expected')
