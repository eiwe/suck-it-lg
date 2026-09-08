"""Runs on the rooted TV; FILES and PUBLIC_KEY are supplied over authenticated SSH."""
import datetime
import os
from pathlib import Path
import shutil

assert os.getuid() == 0
os.umask(0o077)
backup = Path('/var/lib/webosbrew/lg-owner-backup') / ('install-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
backup.mkdir(parents=True)
sshdir = Path('/home/root/.ssh')
sshdir.mkdir(exist_ok=True, parents=True)
sshdir.chmod(0o700)
authorized = sshdir / 'authorized_keys'
if authorized.exists():
    shutil.copy2(authorized, backup / 'authorized_keys')
existing = authorized.read_text() if authorized.exists() else ''
if PUBLIC_KEY not in existing.splitlines():
    authorized.write_text(existing.rstrip('\n') + '\n' + PUBLIC_KEY + '\n')
authorized.chmod(0o600)
for name, content in FILES.items():
    path = Path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        destination = backup / name.lstrip('/')
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
    temporary = path.with_name(path.name + '.owner-tmp')
    temporary.write_text(content)
    temporary.chmod(0o700)
    temporary.replace(path)
for flag in ('webosbrew_sshd_enabled', 'webosbrew_telnet_disabled', 'webosbrew_block_updates'):
    Path('/var/luna/preferences', flag).touch()
os.sync()
print('TV startup files backed up to', backup)
