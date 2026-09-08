#!/usr/bin/env python3
"""Inspect the exact Git index before commit; never print matched secret values."""
import re
import subprocess
import sys

paths = subprocess.check_output(['git', 'ls-files', '--cached', '-z']).decode().split('\0')
patterns = {
    'private key': rb'-----BEGIN (?:OPENSSH |RSA |EC |DSA )?PRIVATE KEY-----',
    'GitHub token': rb'(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})',
    'SSH public key/device identity': rb'ssh-ed25519 AAAA[A-Za-z0-9+/]{30,}',
    'LG pairing credential': rb'["\x27](?:client-key|client_key)["\x27]\s*:\s*["\x27][A-Za-z0-9_-]{8,}',
    'MAC address': rb'(?i)(?:[0-9a-f]{2}:){5}[0-9a-f]{2}',
}
failures = []
for path in filter(None, paths):
    if path.startswith('.private/') or path.endswith(('.key', '.pem', '.pub', '.ipk', '.log', '.tar', '.tgz')):
        failures.append((path, 'private or raw artifact path'))
    data = subprocess.check_output(['git', 'show', ':' + path])
    for label, pattern in patterns.items():
        if re.search(pattern, data):
            failures.append((path, label))
    # Detect the original session's workstation-specific absolute home path.
    if re.search(rb'/home/(?!root/)[A-Za-z0-9_.-]+/', data):
        failures.append((path, 'personal absolute home path'))
for path, label in failures:
    print('FAIL:', path, '-', label)
if failures:
    sys.exit(1)
print('Staged files checked: no matching keys, tokens, pairing credentials, MACs or private artifacts.')
print('This focused scanner supplements manual review; it is not a proof that arbitrary secrets are absent.')
