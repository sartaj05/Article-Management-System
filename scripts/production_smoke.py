"""Run deployment smoke checks against a live Article Studio instance.

This intentionally uses only the Python standard library so it can run from a
release job before application dependencies are fully warmed up.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from urllib.parse import urljoin


def fetch(base_url, path, headers, timeout):
    url = urljoin(base_url.rstrip('/') + '/', path.lstrip('/'))
    request = urllib.request.Request(url, headers={'Accept': 'application/json', **headers})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode('utf-8', errors='replace')
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                payload = {'raw': body[:500]}
            return {'path': path, 'url': url, 'status': response.status, 'ok': 200 <= response.status < 300, 'payload': payload}
    except urllib.error.HTTPError as error:
        body = error.read().decode('utf-8', errors='replace')
        return {'path': path, 'url': url, 'status': error.code, 'ok': False, 'error': body[:500]}
    except (OSError, urllib.error.URLError) as error:
        return {'path': path, 'url': url, 'status': None, 'ok': False, 'error': str(error)}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Check Article Studio deployment health and status endpoints.')
    parser.add_argument('--base-url', default=os.getenv('BASE_URL', 'http://127.0.0.1:8000'))
    parser.add_argument('--timeout', type=float, default=10)
    parser.add_argument('--metrics-token', default=os.getenv('METRICS_TOKEN', ''))
    args = parser.parse_args(argv)

    headers = {'X-Metrics-Token': args.metrics_token} if args.metrics_token else {}
    checks = [fetch(args.base_url, '/health/?verbose=1', {}, args.timeout), fetch(args.base_url, '/status/', {}, args.timeout)]
    if args.metrics_token:
        checks.append(fetch(args.base_url, '/metrics/', headers, args.timeout))
    result = {'base_url': args.base_url.rstrip('/'), 'checks': checks, 'passed': all(item['ok'] for item in checks)}
    print(json.dumps(result, indent=2, default=str))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
