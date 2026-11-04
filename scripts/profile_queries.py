"""Profile one authenticated endpoint and print a compact query report.

Usage: python scripts/profile_queries.py /articles/api/v2/analytics/
"""

import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext


path = sys.argv[1] if len(sys.argv) > 1 else '/health/'
client = Client()
with CaptureQueriesContext(connection) as queries:
    response = client.get(path)
print(f'endpoint={path} status={response.status_code} queries={len(queries)}')
for index, query in enumerate(queries, start=1):
    print(f'{index:03d} {query["sql"][:240]}')
