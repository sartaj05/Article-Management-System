"""Run a sustained, bounded HTTP stress test with CI-friendly thresholds."""

import argparse
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from statistics import mean


def request_once(url, headers, timeout):
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
    values = sorted(values)
    return round(values[min(len(values) - 1, int((len(values) - 1) * fraction))], 2)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Stress-test a read-only Article Studio endpoint.')
    parser.add_argument('--url', default=f"{os.getenv('BASE_URL', 'http://127.0.0.1:8000').rstrip('/')}/health/")
    parser.add_argument('--duration', type=float, default=30, help='Test duration in seconds.')
    parser.add_argument('--concurrency', type=int, default=10)
    parser.add_argument('--timeout', type=float, default=10)
    parser.add_argument('--max-error-rate', type=float, default=0.01)
    parser.add_argument('--max-p95-ms', type=float, default=1000)
    parser.add_argument('--header', action='append', default=[], help='Additional header in Name=Value form; repeatable.')
    args = parser.parse_args(argv)
    if args.duration <= 0 or args.concurrency <= 0:
        parser.error('--duration and --concurrency must be positive')
    headers = {}
    for item in args.header:
        if '=' not in item:
            parser.error('--header must use Name=Value')
        name, value = item.split('=', 1)
        headers[name.strip()] = value.strip()

    deadline = time.perf_counter() + args.duration
    results = []
    lock = threading.Lock()

    def worker():
        while time.perf_counter() < deadline:
            result = request_once(args.url, headers, args.timeout)
            with lock:
                results.append(result)

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        list(executor.map(lambda _worker: worker(), range(args.concurrency)))
    elapsed = time.perf_counter() - started
    latencies = [item['latency_ms'] for item in results]
    failures = [item for item in results if item['error'] or not (200 <= (item['status'] or 0) < 300)]
    error_rate = len(failures) / len(results) if results else 1.0
    p95 = percentile(latencies, .95)
    summary = {
        'url': args.url,
        'duration_seconds': round(elapsed, 3),
        'concurrency': args.concurrency,
        'requests': len(results),
        'requests_per_second': round(len(results) / elapsed, 2) if elapsed else 0,
        'error_rate': round(error_rate, 4),
        'p95_ms': p95,
        'mean_ms': round(mean(latencies), 2) if latencies else None,
        'thresholds': {'max_error_rate': args.max_error_rate, 'max_p95_ms': args.max_p95_ms},
        'failures': failures[:10],
    }
    summary['passed'] = bool(results) and error_rate <= args.max_error_rate and p95 is not None and p95 <= args.max_p95_ms
    print(json.dumps(summary, indent=2, default=str))
    return 0 if summary['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
