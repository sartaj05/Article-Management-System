from django.test import TestCase
from rest_framework.test import APIClient

from .models import CustomUser, Workspace, WorkspaceBillingContract, WorkspaceMembership


class BillingContractTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = CustomUser.objects.create_user(username='contract-admin', email='contract@example.com', password='StrongPass123!', role='Admin')
        self.workspace = Workspace.objects.create(name='Contract newsroom', slug='contract-newsroom', owner=self.admin)
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.admin, role='owner')
        self.client.force_authenticate(self.admin)

    def test_contract_update_exposes_seat_and_contract_terms(self):
        response = self.client.patch(
            '/api/workspaces/contract-newsroom/billing/contract/',
            {'contract_type': 'enterprise', 'status': 'active', 'seat_commitment': 25, 'monthly_commitment': '4999.00', 'purchase_order': 'PO-2026-001', 'tax_id': 'GST-123', 'renewal_at': '2027-11-01'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['contract']['contract_type'], 'enterprise')
        self.assertEqual(response.data['contract']['purchase_order'], 'PO-2026-001')
        self.assertEqual(response.data['seat_usage']['committed'], 25)
        self.assertTrue(WorkspaceBillingContract.objects.filter(workspace=self.workspace, status='active').exists())

    def test_contract_cannot_commit_fewer_seats_than_members(self):
        response = self.client.patch(
            '/api/workspaces/contract-newsroom/billing/contract/', {'seat_commitment': 0}, format='json',
        )
        self.assertEqual(response.status_code, 400)
