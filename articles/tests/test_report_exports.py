import csv
from io import StringIO

from rest_framework.test import APITestCase

from users.models import CustomUser
from ..models import Article


class ReportExportTests(APITestCase):
    def setUp(self):
        self.author = CustomUser.objects.create_user(username='report-author', email='report-author@example.com', password='Password123!', role='Journalist')
        Article.objects.create(title='Report article test', content='Content', author=self.author, agreed_to_terms=True)

    def test_journalist_can_download_own_article_csv(self):
        self.client.force_authenticate(self.author)
        response = self.client.get('/articles/api/v2/reports/articles/')
        self.assertEqual(response.status_code, 200)
        rows = list(csv.reader(StringIO(response.content.decode())))
        self.assertEqual(rows[0][0], 'id')
        self.assertEqual(rows[1][1], 'Report article test')
