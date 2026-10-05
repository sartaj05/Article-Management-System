from django.test import TestCase
from rest_framework.test import APIClient

from users.models import CustomUser
from ..models import ExperimentEvent
from ..models import Article


class ExperimentFeatureTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.editor = CustomUser.objects.create_user(
            username='experiment-editor', email='experiment-editor@example.com', password='StrongPass123!', role='Editor',
        )
        self.article = Article.objects.create(
            title='Experiment article', content='Experiment content', author=self.editor,
            author_name=self.editor.username, email=self.editor.email, agreed_to_terms=True,
            workflow_status='published', status='published', is_visible=True,
        )
        self.client.force_authenticate(self.editor)

    def test_editor_can_run_experiment_and_read_results(self):
        response = self.client.post('/articles/api/v2/experiments/', {
            'article': self.article.id, 'name': 'Headline test', 'experiment_type': 'headline',
        }, format='json')
        self.assertEqual(response.status_code, 201)
        experiment_id = response.data['id']

        for label, headline in [('A', 'Original headline'), ('B', 'Alternative headline')]:
            response = self.client.post(f'/articles/api/v2/experiments/{experiment_id}/variants/', {
                'label': label, 'headline': headline,
            }, format='json')
            self.assertEqual(response.status_code, 201)

        response = self.client.post(f'/articles/api/v2/experiments/{experiment_id}/start/')
        self.assertEqual(response.status_code, 200)
        self.client.force_authenticate(None)

        response = self.client.post(f'/articles/api/v2/experiments/{experiment_id}/assign/', {'visitor_key': 'reader-1'}, format='json')
        self.assertEqual(response.status_code, 200)
        response = self.client.post(f'/articles/api/v2/experiments/{experiment_id}/events/', {
            'visitor_key': 'reader-1', 'event_type': 'view',
        }, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(ExperimentEvent.objects.count(), 1)

        self.client.force_authenticate(self.editor)
        response = self.client.get(f'/articles/api/v2/experiments/{experiment_id}/results/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 2)
