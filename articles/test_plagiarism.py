from rest_framework.test import APITestCase

from users.models import CustomUser
from .models import Article, PlagiarismCheck


class PlagiarismTests(APITestCase):
    def setUp(self):
        self.author = CustomUser.objects.create_user(username='plagiarism-author', email='plagiarism@example.com', password='Password123!', role='Journalist')
        self.source = 'This article contains a long and distinctive sentence that should be detected as duplicated content.'
        Article.objects.create(title='Published source article', content=self.source, author=self.author, agreed_to_terms=True, workflow_status='published', status='published', is_visible=True)
        self.article = Article.objects.create(title='Plagiarism target article', content=self.source, author=self.author, agreed_to_terms=True)

    def test_author_can_run_plagiarism_check(self):
        self.client.force_authenticate(self.author)
        response = self.client.post(f'/articles/api/v2/articles/{self.article.id}/plagiarism/')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['status'], 'duplicate')
        self.assertTrue(PlagiarismCheck.objects.filter(article=self.article).exists())
