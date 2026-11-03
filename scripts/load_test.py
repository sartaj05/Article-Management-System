"""Small dependency-free HTTP load probe for staging and production smoke tests.

Use a low request count first. This is a measurement tool, not a replacement
for a dedicated load platform such as k6 or Locust.
"""

import argparse
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin


def run_request(url, headers, timeout):
    started = time.perf_counter()
    request = urllib.request.Request(url, headers={'Accept': 'application/json', **headers})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read(256)
            return {'status': response.status, 'latency_ms': (time.perf_counter() - started) * 1000, 'error': None}
    except urllib.error.HTTPError as error:
        return {'status': error.code, 'latency_ms': (time.perf_counter() - started) * 1000, 'error': f'HTTP {error.code}'}
    except (OSError, urllib.error.URLError) as error:
        return {'status': None, 'latency_ms': (time.perf_counter() - started) * 1000, 'error': str(error)}


def percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((len(ordered) - 1) * fraction)))
    return round(ordered[index], 2)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Run a bounded concurrent HTTP load probe.')
    parser.add_argument('--url', default=urljoin(os.getenv('BASE_URL', 'http://127.0.0.1:8000').rstrip('/') + '/', 'health/'))
    parser.add_argument('--requests', type=int, default=50)
    parser.add_argument('--concurrency', type=int, default=5)
    parser.add_argument('--timeout', type=float, default=10)
    parser.add_argument('--header', action='append', default=[], help='Additional header in Name=Value form; repeatable.')
    args = parser.parse_args(argv)
    if args.requests < 1 or args.concurrency < 1:
        parser.error('--requests and --concurrency must be positive')
    headers = {}
    for item in args.header:
        if '=' not in item:
            parser.error('--header must use Name=Value')
        name, value = item.split('=', 1)
        headers[name.strip()] = value.strip()

    started = time.perf_counter()
    results = []
    with ThreadPoolExecutor(max_workers=min(args.concurrency, args.requests)) as executor:
        futures = [executor.submit(run_request, args.url, headers, args.timeout) for _ in range(args.requests)]
        for future in as_completed(futures):
            results.append(future.result())
    elapsed = time.perf_counter() - started
    latencies = [item['latency_ms'] for item in results]
    statuses = {}
    for item in results:
        key = str(item['status']) if item['status'] is not None else 'network_error'
        statuses[key] = statuses.get(key, 0) + 1
    failures = [item for item in results if item['error'] or not (200 <= (item['status'] or 0) < 300)]
    summary = {
        'url': args.url,
        'requests': len(results),
        'concurrency': min(args.concurrency, args.requests),
        'elapsed_seconds': round(elapsed, 3),
        'requests_per_second': round(len(results) / elapsed, 2) if elapsed else 0,
        'status_counts': statuses,
        'latency_ms': {'min': round(min(latencies), 2) if latencies else None, 'mean': round(statistics.mean(latencies), 2) if latencies else None, 'p50': percentile(latencies, .50), 'p95': percentile(latencies, .95), 'max': round(max(latencies), 2) if latencies else None},
        'failures': failures[:10],
        'passed': not failures and len(results) == args.requests,
    }
    print(json.dumps(summary, indent=2, default=str))
    return 0 if summary['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
