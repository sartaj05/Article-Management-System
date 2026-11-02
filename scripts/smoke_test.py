"""Run a small, dependency-free smoke test against a deployed Article Studio instance."""

import os
import sys
import urllib.error
import urllib.request


def check_endpoint(base_url, path):
    url = f"{base_url.rstrip('/')}{path}"
    request = urllib.request.Request(url, headers={'User-Agent': 'article-studio-smoke-test/1.0'})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read().decode('utf-8', errors='replace')
            if response.status != 200:
                raise RuntimeError(f'{url} returned HTTP {response.status}')
            return body
    except (urllib.error.URLError, TimeoutError) as error:
        raise RuntimeError(f'Unable to reach {url}: {error}') from error


def main():
    base_url = os.getenv('BASE_URL')
    if not base_url:
        print('BASE_URL is required', file=sys.stderr)
        return 2
    basic = check_endpoint(base_url, '/health/')
    if '"status":"healthy"' not in basic.replace(' ', ''):
        raise RuntimeError('Basic health endpoint did not report healthy')
    verbose = check_endpoint(base_url, '/health/?verbose=1')
    if '"database":"ok"' not in verbose.replace(' ', ''):
        raise RuntimeError('Verbose health endpoint did not report database ok')
    print(f'Smoke test passed for {base_url}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
