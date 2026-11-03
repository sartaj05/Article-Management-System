from django.test import SimpleTestCase
from django.urls import Resolver404, resolve


class LegacyRouteTests(SimpleTestCase):
    def test_duplicate_submit_route_is_removed(self):
        with self.assertRaises(Resolver404):
            resolve('/articles/submit/')

    def test_missing_template_legacy_routes_are_removed(self):
        for path in ('/articles/drafts/', '/articles/archive/', '/articles/status/1/'):
            with self.subTest(path=path), self.assertRaises(Resolver404):
                resolve(path)
