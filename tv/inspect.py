"""Read-only inspection, plus two TCP connection probes; emits private JSON."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time


def run(*args):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=10)
        return {'exit': p.returncode, 'output': p.stdout.strip(), 'error': p.stderr.strip()}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'exit': -1, 'output': '', 'error': str(exc)}


report = {
    'checked_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    'uid': os.getuid(), 'ssh_client_ip': os.environ.get('SSH_CONNECTION', '').split(' ')[0],
    'os_release': Path('/etc/os-release').read_text(),
    'uptime': Path('/proc/uptime').read_text().strip(),
    'tools': {name: shutil.which(name) for name in ('iptables', 'systemctl', 'mount', 'awk', 'luna-send')},
    'homebrew_dropbear': os.access('/media/developer/apps/usr/palm/services/org.webosbrew.hbchannel.service/bin/dropbear', os.X_OK),
    'dmost_unit_exists': Path('/etc/systemd/system/dmost.service').exists(),
    'interfaces': sorted(p.name for p in Path('/sys/class/net').iterdir()),
    'ipv4_output': run('iptables', '-S', 'OUTPUT'),
    'ipv4_privacy_rules': run('iptables', '-S', 'LG_OWNER_PRIVACY'),
    'ipv4_counters': run('iptables', '-L', 'LG_OWNER_PRIVACY', '-n', '-v'),
    'dmost': run('systemctl', 'show', 'dmost.service', '-p', 'MainPID', '-p', 'LoadState', '-p', 'ActiveState'),
    'ipv6_disabled': {}, 'remote_access': [], 'connectivity_tests': {},
}
for p in Path('/proc/sys/net/ipv6/conf').iterdir():
    if p.name not in ('all', 'default', 'lo'):
        report['ipv6_disabled'][p.name] = (p / 'disable_ipv6').read_text().strip()
for p in Path('/proc').iterdir():
    if not p.name.isdigit():
        continue
    try:
        name = (p / 'comm').read_text().strip()
        if name in ('dropbear', 'telnetd'):
            report['remote_access'].append({'name': name,
                'argv': (p / 'cmdline').read_bytes().decode().strip('\0').split('\0')})
    except OSError:
        pass
for label, family, target in [('ipv4', socket.AF_INET, ('1.1.1.1', 443)),
                               ('ipv6', socket.AF_INET6, ('2606:4700:4700::1111', 443))]:
    with socket.socket(family, socket.SOCK_STREAM) as sock:
        sock.settimeout(2)
        try:
            sock.connect(target)
            report['connectivity_tests'][label] = {'connected': True}
        except OSError as exc:
            report['connectivity_tests'][label] = {'connected': False, 'error': str(exc)}
print(json.dumps(report, indent=2))
