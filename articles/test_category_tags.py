from rest_framework.test import APITestCase

from users.models import CustomUser
from .models import Article, Category, Tag


class CategoryTagTests(APITestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_user(username='taxonomy-admin', email='taxonomy@example.com', password='Password123!', role='Admin')
        self.journalist = CustomUser.objects.create_user(username='taxonomy-writer', email='writer-taxonomy@example.com', password='Password123!', role='Journalist')

    def test_admin_manages_taxonomy_and_assigns_it_to_article(self):
        self.client.force_authenticate(self.admin)
        category_response = self.client.post('/articles/api/v2/categories/', {'name': 'Technology', 'description': 'Technology news'}, format='json')
        tag_response = self.client.post('/articles/api/v2/tags/', {'name': 'Python'}, format='json')
        self.assertEqual(category_response.status_code, 201)
        self.assertEqual(tag_response.status_code, 201)
        category = Category.objects.get(name='Technology')
        tag = Tag.objects.get(name='Python')
        article = Article.objects.create(title='Taxonomy article test', content='Content', author=self.journalist, agreed_to_terms=True)
        response = self.client.patch(
            f'/articles/api/v2/articles/{article.id}/',
            {'category_ref': category.id, 'tag_objects': [tag.id]},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        article.refresh_from_db()
        self.assertEqual(article.category_ref_id, category.id)
        self.assertEqual(list(article.tag_objects.values_list('id', flat=True)), [tag.id])
