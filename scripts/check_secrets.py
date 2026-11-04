"""Small CI guard for accidentally committed credentials.

This is intentionally conservative and ignores examples, tests, and generated
artifacts. Provider secrets should still be rotated if a scan is ever triggered.
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATTERNS = [
    re.compile(r'(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*["\'][^"\']{20,}["\']'),
    re.compile(r'(?i)-----BEGIN (RSA|EC|OPENSSH|PRIVATE) KEY-----'),
    re.compile(r'(?i)sk_live_[0-9a-zA-Z]{16,}'),
]
IGNORED = ('\.env.example', 'tests/', 'test_', 'coverage/', 'staticfiles/', 'node_modules/')


def main():
    files = subprocess.check_output(['git', 'ls-files'], cwd=ROOT, text=True).splitlines()
    findings = []
    for name in files:
        if any(marker in name for marker in IGNORED):
            continue
        path = ROOT / name
        try:
            text = path.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError):
            continue
        for line_number, line in enumerate(text.splitlines(), 1):
            if '{{' in line or '{%' in line:
                continue
            if any(pattern.search(line) for pattern in PATTERNS):
                findings.append(f'{name}:{line_number}')
    if findings:
        print('Potential committed secret(s):', *findings, sep='\n', file=sys.stderr)
        return 1
    print('Secret scan passed.')
    return 0


raise SystemExit(main())
