from django.test import TestCase
from rest_framework.test import APIClient

from users.models import CustomUser
from ..models import Article, ExperimentAssignment, ExperimentEvent


class ExperimentCompletionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.editor = CustomUser.objects.create_user(username='experiment-completer', email='experiment-completer@example.com', password='StrongPass123!', role='Editor')
        self.article = Article.objects.create(title='Experiment completion article', content='Content', author=self.editor, agreed_to_terms=True, workflow_status='published', status='published', is_visible=True)
        self.client.force_authenticate(self.editor)

    def test_running_experiment_selects_winner_and_completes(self):
        response = self.client.post('/articles/api/v2/experiments/', {'article': self.article.id, 'name': 'Completion test', 'experiment_type': 'headline'}, format='json')
        experiment_id = response.data['id']
        variant_ids = []
        for label in ('A', 'B'):
            response = self.client.post(f'/articles/api/v2/experiments/{experiment_id}/variants/', {'label': label, 'headline': f'Headline {label}'}, format='json')
            variant_ids.append(response.data['id'])
        self.client.post(f'/articles/api/v2/experiments/{experiment_id}/start/')
        self.client.force_authenticate(None)
        for visitor in ('reader-1', 'reader-2'):
            self.client.post(f'/articles/api/v2/experiments/{experiment_id}/assign/', {'visitor_key': visitor}, format='json')
        assignments = list(ExperimentAssignment.objects.filter(experiment_id=experiment_id).order_by('id'))
        ExperimentEvent.objects.create(assignment=assignments[0], event_type='view')
        ExperimentEvent.objects.create(assignment=assignments[0], event_type='read')
        ExperimentEvent.objects.create(assignment=assignments[1], event_type='view')
        self.client.force_authenticate(self.editor)
        response = self.client.post(f'/articles/api/v2/experiments/{experiment_id}/complete/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'completed')
        self.assertEqual(response.data['winning_variant'], assignments[0].variant_id)
