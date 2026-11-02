from django.core.cache import cache
from django.test import SimpleTestCase


class PerformanceConfigurationTests(SimpleTestCase):
    def test_cache_can_be_written_and_cleared(self):
        cache.set('performance-test', 'ok')
        self.assertEqual(cache.get('performance-test'), 'ok')
        cache.delete('performance-test')
        self.assertIsNone(cache.get('performance-test'))
