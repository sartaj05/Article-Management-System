from rest_framework.test import APITestCase

from users.models import CustomUser
from ..models import Article, ArticleReaction


class ReactionTests(APITestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(username='reaction-user', email='reaction@example.com', password='Password123!', role='Journalist')
        self.article = Article.objects.create(title='Reaction article test', content='Content', author=self.user, agreed_to_terms=True)

    def test_user_can_toggle_and_change_article_reaction(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(f'/articles/api/v2/articles/{self.article.id}/reactions/', {'reaction': 'helpful'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['my_reaction'], 'helpful')
        response = self.client.post(f'/articles/api/v2/articles/{self.article.id}/reactions/', {'reaction': 'informative'}, format='json')
        self.assertEqual(response.data['my_reaction'], 'informative')
        self.assertEqual(ArticleReaction.objects.get(article=self.article, user=self.user).reaction, 'informative')
