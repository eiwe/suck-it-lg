#!/usr/bin/env python3
"""Owner-controlled webOS privacy setup. Local dependencies: Python 3 + OpenSSH."""
import argparse
import copy
import datetime
import ipaddress
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
STATE = ROOT / '.private'
OPTIONS = {
    'watchedListCollection': 'off', 'usageCare': False,
    'dbgLogUpload': False, 'faultLogUpload': False,
    'thirdPartyCookie': 'off', 'livePromotion': 'off', 'turnOnByVoice': 'off',
}
GENERAL = {
    'aiNudge': 'off', 'voiceLongDistance': 'off', 'screenSaverAd': 'off',
    'homePromotion': 'off', 'launchEulaByHome': False,
    'doNotSellMyPersonalInformation': 'on',
}
CONSENT_KEYS = ['eulaStatus', 'eulaInfo', 'eulaInfoNetwork']


def private_ipv4(value):
    address = ipaddress.IPv4Address(value)
    networks = ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')
    if not any(address in ipaddress.IPv4Network(n) for n in networks):
        raise ValueError('Use an RFC1918 private IPv4 address on your own LAN')
    return str(address)


def save_private(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(json.dumps(data, indent=2) + '\n')
    path.chmod(0o600)


def stamp():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')


def config():
    data = json.loads((STATE / 'config.json').read_text())
    data['host'] = private_ipv4(data['host'])
    data['admin_ipv4'] = private_ipv4(data['admin_ipv4'])
    return data


def ssh_args(c):
    return ['ssh', '-i', str(STATE / 'owner-ed25519'),
            '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes',
            '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=5',
            '-o', 'UserKnownHostsFile=' + str(STATE / 'known_hosts'),
            'root@' + c['host']]


def remote(c, command, *, stdin=None, tty=False, timeout=120):
    argv = ssh_args(c)
    if tty:
        argv.insert(1, '-tt')
    p = subprocess.run(argv + [command], input=stdin, text=True,
                       capture_output=True, timeout=timeout)
    if p.returncode:
        raise RuntimeError('SSH command failed: ' + p.stderr.strip() + '\n' + p.stdout.strip())
    return p.stdout


def luna(c, method, payload):
    command = '/usr/bin/luna-send -w 5000 -n 1 -f luna://com.webos.settingsservice/'
    command += method + ' ' + shlex.quote(json.dumps(payload, separators=(',', ':')))
    data = json.loads(remote(c, command, tty=True, timeout=15))
    if data.get('returnValue') is not True:
        raise RuntimeError('LG settings API rejected request: ' + json.dumps(data))
    return data


def consent_state(c):
    return luna(c, 'getSystemSettings', {'keys': CONSENT_KEYS})['settings']


def decline_consents(original):
    """Preserve unknown metadata; reject an unexpected schema instead of guessing."""
    data = copy.deepcopy(original)
    status = data['eulaStatus']
    flags = [k for k in status if k.endswith('Allowed')]
    if not flags:
        raise ValueError('No consent flags found; unsupported schema')
    for key in flags:
        if not isinstance(status[key], bool):
            raise ValueError('Unexpected consent flag type: ' + key)
        status[key] = False
    for group in ('eulaInfo', 'eulaInfoNetwork'):
        documents = data[group]['eulaList']
        if not isinstance(documents, list):
            raise ValueError('Unexpected agreement list')
        for document in documents:
            if not isinstance(document.get('accepted'), bool):
                raise ValueError('Unexpected agreement acceptance field')
            document['accepted'] = False
            document['updated'] = True
        data[group]['updated'] = True
    return data


def consents_declined(data):
    try:
        decline_consents(data)  # Validate the actual schema, not just empty results.
        flags = [v for k, v in data['eulaStatus'].items() if k.endswith('Allowed')]
        docs = [d for g in ('eulaInfo', 'eulaInfoNetwork') for d in data[g]['eulaList']]
        return all(v is False for v in flags) and all(d['accepted'] is False for d in docs)
    except (KeyError, TypeError, ValueError):
        return False


def inspect(c):
    return json.loads(remote(c, 'python3 -', stdin=(ROOT / 'tv/inspect.py').read_text()))


def preflight(c, allow_untested=False):
    data = inspect(c)
    if data['uid'] != 0:
        raise RuntimeError('The TV is not rooted')
    if data['ssh_client_ip'] != c['admin_ipv4']:
        raise RuntimeError('SSH client address differs from admin_ipv4; firewall installation would lock you out')
    if 'VERSION_ID=10.3.0\n' not in data['os_release'] and not allow_untested:
        raise RuntimeError('Only webOS 10.3.0 was tested. Review compatibility before --allow-untested')
    for tool in ('iptables', 'systemctl', 'mount', 'awk', 'luna-send'):
        if not data['tools'].get(tool):
            raise RuntimeError('Missing TV prerequisite: ' + tool)
    if not data['homebrew_dropbear']:
        raise RuntimeError('Expected Homebrew Channel Dropbear executable is missing')
    unknown = set(data['interfaces']) - {'lo', 'eth0', 'wlan0', 'p2p0', 'sit0'}
    if unknown:
        raise RuntimeError('Review IPv6 handling for unfamiliar interfaces: ' + ', '.join(sorted(unknown)))
    if data['ipv4_output']['exit'] != 0:
        raise RuntimeError('The IPv4 firewall is unavailable')
    return data


def snapshot(c, before):
    folder = STATE / ('backup-' + stamp())
    settings = {'consents': consent_state(c)}
    for category, values in [('option', OPTIONS), ('general', GENERAL)]:
        settings[category] = luna(c, 'getSystemSettings',
                                 {'category': category, 'keys': list(values)})['settings']
        if not set(values).issubset(settings[category]):
            raise RuntimeError('Missing settings in ' + category + '; stop and review compatibility')
    decline_consents(settings['consents'])
    save_private(folder / 'settings.json', settings)
    save_private(folder / 'inspection.json', before)
    print('Private backup:', folder)
    return settings


def render_files(c, channels):
    names = ['10-owner-ssh'] + (['20-disable-lg-channels'] if channels else [])
    files = {'/var/lib/webosbrew/init.d/' + name: (ROOT / 'tv' / name).read_text() for name in names}
    files['/var/lib/webosbrew/init.d/00-network-privacy'] = (
        ROOT / 'tv/00-network-privacy.in').read_text().replace('@ADMIN_IPV4@', private_ipv4(c['admin_ipv4']))
    for name in ['restore-network.sh', 'restore-lg-channels.sh']:
        files['/var/lib/webosbrew/lg-owner/' + name] = (ROOT / 'tv' / name).read_text()
    return files


def install(c, args):
    before = preflight(c, args.allow_untested)
    if args.disable_channels and not before['dmost_unit_exists']:
        raise RuntimeError('This TV does not have the tested LG Channels service')
    # Reject another firewall rather than assuming our rule will take precedence.
    rules = before['ipv4_output']['output'].splitlines()
    if rules not in (['-P OUTPUT ACCEPT'], ['-P OUTPUT ACCEPT', '-A OUTPUT -j LG_OWNER_PRIVACY']):
        raise RuntimeError('Existing OUTPUT rules need manual review; nothing changed')
    if len(rules) > 1:
        remote(c, 'iptables -C LG_OWNER_PRIVACY -d ' + c['admin_ipv4'] + ' -p tcp --sport 22 -j ACCEPT')
    settings = snapshot(c, before)
    public_key = (STATE / 'owner-ed25519.pub').read_text().strip()
    files = render_files(c, args.disable_channels)
    payload = 'FILES = ' + repr(files) + '\nPUBLIC_KEY = ' + repr(public_key) + '\n'
    payload += (ROOT / 'tv/install-files.py').read_text()
    print(remote(c, 'python3 -', stdin=payload).strip())
    remote(c, 'sh /var/lib/webosbrew/init.d/10-owner-ssh')
    # Prove that a new key-only connection works before disabling current telnet.
    if remote(c, 'id -u').strip() != '0':
        raise RuntimeError('Fresh root SSH connection failed')
    remote(c, 'python3 -', stdin="""import os, signal
from pathlib import Path
for p in Path('/proc').iterdir():
    if not p.name.isdigit(): continue
    try:
        if (p/'comm').read_text().strip() == 'telnetd': os.kill(int(p.name), signal.SIGTERM)
    except (OSError, ProcessLookupError): pass
""")
    for category, values in [('option', OPTIONS), ('general', GENERAL)]:
        luna(c, 'setSystemSettings', {'category': category, 'settings': values})
    luna(c, 'setSystemSettings', {'settings': decline_consents(settings['consents'])})
    if not consents_declined(consent_state(c)):
        raise RuntimeError('Consent readback failed; backup retained, do not assume opt-out succeeded')
    remote(c, 'rm -f /var/luna/preferences/lg_owner_network_privacy_off; sh /var/lib/webosbrew/init.d/00-network-privacy')
    if args.disable_channels:
        remote(c, 'rm -f /var/luna/preferences/lg_owner_channels_enabled; sh /var/lib/webosbrew/init.d/20-disable-lg-channels')
    remote(c, 'sync')
    verify(c, args.disable_channels)
    print('Installation checked. Restart the TV when convenient, then run verify again.')


def verify(c, require_channels=False):
    data = inspect(c)
    data['consents_api'] = consent_state(c)
    checks = {
        'root': data['uid'] == 0,
        'all_consents_declined': consents_declined(data['consents_api']),
        'firewall_first_output_rule': data['ipv4_output']['exit'] == 0 and
            data['ipv4_output']['output'].splitlines()[1:2] == ['-A OUTPUT -j LG_OWNER_PRIVACY'],
        'no_telnet': not any(p['name'] == 'telnetd' for p in data['remote_access']),
        'ssh_password_auth_disabled': any(p['name'] == 'dropbear' for p in data['remote_access']) and
            all('-s' in p['argv'] for p in data['remote_access'] if p['name'] == 'dropbear'),
        'ipv6_external_disabled': bool(data['ipv6_disabled']) and all(v == '1' for v in data['ipv6_disabled'].values()),
        'public_ipv4_probe_blocked': data['connectivity_tests']['ipv4']['connected'] is False,
        'public_ipv6_probe_blocked': data['connectivity_tests']['ipv6']['connected'] is False,
    }
    rules = data['ipv4_privacy_rules']['output'].splitlines()
    checks['firewall_expected_rules'] = data['ipv4_privacy_rules']['exit'] == 0 and rules == [
        '-N LG_OWNER_PRIVACY', '-A LG_OWNER_PRIVACY -o lo -j ACCEPT',
        '-A LG_OWNER_PRIVACY -d ' + c['admin_ipv4'] + '/32 -p tcp -m tcp --sport 22 -j ACCEPT',
        '-A LG_OWNER_PRIVACY -p udp -m udp --sport 68 --dport 67 -j ACCEPT',
        '-A LG_OWNER_PRIVACY -j DROP']
    for category, expected in [('option', OPTIONS), ('general', GENERAL)]:
        actual = luna(c, 'getSystemSettings', {'category': category, 'keys': list(expected)})['settings']
        data[category + '_api'] = actual
        for key, value in expected.items():
            if key != 'dbgLogUpload':
                checks[category + '.' + key] = actual.get(key) == value
    if require_channels:
        checks['channels_masked_and_stopped'] = all(x in data['dmost']['output'].splitlines()
            for x in ['MainPID=0', 'LoadState=masked', 'ActiveState=inactive'])
    data['checks'] = checks
    data['known_limitations'] = ['Startup hooks leave an early-boot gap.',
        'dbgLogUpload may reset to true after restart.',
        'Blocked probes do not prove that all local data collection stopped.']
    target = STATE / ('verification-' + stamp() + '.json')
    save_private(target, data)
    for name, result in checks.items():
        print(('PASS ' if result else 'FAIL ') + name)
    print('dbgLogUpload:', data['option_api'].get('dbgLogUpload'), '(known reboot reset)')
    print('Private report:', target)
    if not all(checks.values()):
        raise RuntimeError('Verification failed; inspect the private report')


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    init = sub.add_parser('init', help='Create private configuration and a dedicated SSH key')
    init.add_argument('--host', required=True, type=private_ipv4)
    init.add_argument('--admin-ip', required=True, type=private_ipv4)
    sub.add_parser('bootstrap-commands', help='Print public-key commands to paste into the TV root shell')
    sub.add_parser('trust-host', help='Interactive first SSH connection; verify the fingerprint')
    sub.add_parser('shell', help='Open an interactive owner root shell using the dedicated key')
    sub.add_parser('preflight', help='Read-only prerequisite check on tested webOS version')
    p = sub.add_parser('install', help='Back up and apply HDMI-only privacy configuration')
    p.add_argument('--disable-channels', action='store_true')
    p.add_argument('--allow-untested', action='store_true', help='Permit another webOS version after manual review')
    p = sub.add_parser('verify', help='Read settings, firewall and service state; probe public connectivity')
    p.add_argument('--channels', action='store_true')
    sub.add_parser('restore-network', help='Disable network block now and on subsequent boots')
    sub.add_parser('restore-channels', help='Restore LG Channels backend only')
    p = sub.add_parser('restore-settings', help='Restore a local settings backup; consents require an explicit flag')
    p.add_argument('backup', type=Path, help='Path to a private backup settings.json')
    p.add_argument('--include-consents', action='store_true', help='Also restore previous agreement acceptance, potentially opting back in')
    args = parser.parse_args()
    if args.action == 'init':
        STATE.mkdir(exist_ok=True, mode=0o700)
        STATE.chmod(0o700)
        if (STATE / 'config.json').exists() or (STATE / 'owner-ed25519').exists():
            raise RuntimeError('Private configuration or key already exists; refusing to replace it')
        subprocess.run(['ssh-keygen', '-t', 'ed25519', '-N', '', '-C', 'lg-webos-privacy-owner',
                        '-f', str(STATE / 'owner-ed25519')], check=True)
        save_private(STATE / 'config.json', {'host': args.host, 'admin_ipv4': args.admin_ip})
        print('Run bootstrap-commands next. Private material is under .private/.')
        return
    c = config()
    if args.action == 'bootstrap-commands':
        key = (STATE / 'owner-ed25519.pub').read_text().strip()
        print('Paste into an existing root shell on your own TV, one line at a time:\n')
        print('umask 077; mkdir -p /home/root/.ssh /var/lib/webosbrew/sshd')
        print('touch /home/root/.ssh/authorized_keys; chmod 700 /home/root/.ssh; chmod 600 /home/root/.ssh/authorized_keys')
        print('grep -qxF ' + shlex.quote(key) + ' /home/root/.ssh/authorized_keys || printf \'%s\\n\' ' +
              shlex.quote(key) + ' >> /home/root/.ssh/authorized_keys')
        print('touch /var/luna/preferences/webosbrew_sshd_enabled')
        print('/media/developer/apps/usr/palm/services/org.webosbrew.hbchannel.service/bin/dropbear -R -s -j -k')
        print('\nIf port 22 is already in use, keep the running daemon and try trust-host; do not kill your only access.')
    elif args.action == 'trust-host':
        argv = ssh_args(c)
        argv[argv.index('StrictHostKeyChecking=yes')] = 'StrictHostKeyChecking=ask'
        argv[argv.index('BatchMode=yes')] = 'BatchMode=no'
        argv[1:1] = ['-o', 'PasswordAuthentication=no', '-o', 'KbdInteractiveAuthentication=no']
        subprocess.run(argv + ['id -u'], check=True)
    elif args.action == 'preflight':
        data = preflight(c)
        print(data['os_release'].strip())
        print('Root, administrator address, expected interfaces and required tools checked.')
    elif args.action == 'shell':
        subprocess.run(['ssh', '-t'] + ssh_args(c)[1:], check=True)
    elif args.action == 'install':
        install(c, args)
    elif args.action == 'verify':
        verify(c, args.channels)
    elif args.action == 'restore-settings':
        settings = json.loads(args.backup.read_text())
        snapshot(c, inspect(c))
        for category in ('option', 'general'):
            luna(c, 'setSystemSettings', {'category': category, 'settings': settings[category]})
        if args.include_consents:
            decline_consents(settings['consents'])  # Schema validation only.
            luna(c, 'setSystemSettings', {'settings': settings['consents']})
        print('Settings restored. Network, SSH and startup hooks are unchanged.')
    else:
        script = {'restore-network': 'restore-network.sh', 'restore-channels': 'restore-lg-channels.sh'}[args.action]
        print(remote(c, 'sh /var/lib/webosbrew/lg-owner/' + script).strip())


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as exc:
        print('ERROR:', exc, file=sys.stderr)
        sys.exit(1)
