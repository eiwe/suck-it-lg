# LG webOS privacy for an HDMI-only TV

Use a rooted LG TV as an HDMI display while retaining owner-controlled SSH access. This project records a working LG C2 setup and provides scripts to reproduce its privacy settings, network restrictions, and LG Channels service block.

**Tested hardware:** LG OLED55C2AUA, firmware **33.31.24**, webOS **10.3.0-2504 / webOS 25**, Homebrew Channel **0.7.3**, September 8, 2026. Other models and firmware need separate validation. The installer checks the webOS version and several prerequisites; it cannot establish that a different TV is compatible merely because those checks pass.

**Best protection for this use case:** unplug the LG's Ethernet cable and disable its Wi-Fi. Keep your Apple TV, console, or streaming box connected to the network independently. Root is useful for maintenance and suppressing unwanted services, but physical network disconnection requires no jailbreak.

## What it changes

| Area | Result |
| --- | --- |
| Agreements | Declines every existing `*Allowed` flag and agreement in LG's authoritative settings database, preserving metadata. |
| Viewing and advertising | Disables watched-list collection, Usage Care, third-party cookies, live promotions, home/screen-saver ads and AI nudges; enables the do-not-sell preference. |
| Voice settings | Disables voice wake and long-distance voice settings. This is a software setting, not a physical microphone disconnect. |
| Diagnostics | Requests debug/fault-log upload off. **Debug upload resets to true after reboot on the tested C2.** |
| IPv4 | Drops outbound traffic except loopback, DHCP, and SSH replies to one administrator workstation. |
| IPv6 | Disables IPv6 on the C2's external interfaces; leaves loopback available. |
| Remote maintenance | Dedicated owner SSH key; SSH passwords and forwarding disabled; Telnet disabled. Existing authorized keys are preserved. |
| Updates | Enables Homebrew's firmware-update block to preserve root. This also prevents normal firmware security updates until you deliberately change the setup. |
| LG Channels, optional | Stops and masks the dedicated `dmost.service` backend using a reversible bind mount. |

The TV's own streaming apps, app downloads, casting, SSAP pairing, network time, and other network services will not work with this firewall. HDMI display use does not require those services. The Apple TV's network connection is independent.

### Limits of the result

- Homebrew startup hooks run after part of webOS has already started. There is an **early-boot gap** for network access and potentially for the LG Channels invitation. A router-enforced IPv4/IPv6 block or physical disconnection closes the network gap.
- A few blocked TCP probes plus firewall inspection verify the configured restriction; they are not an exhaustive traffic capture or proof of zero local data collection.
- Disabling preferences does not demonstrate that every proprietary LG component honors them. That is why this setup also blocks uploads at the network layer.
- Root does not unlock arbitrary hardware capabilities, guarantee firmware downgrades, or provide a supported replacement OS. Do not overwrite signed firmware partitions.
- Keep OLED protection functions, including pixel cleaning and screen protection, intact. This project does not alter them.

## Requirements

- Your own compatible LG TV, already rooted with Homebrew Channel installed.
- A trusted LAN for the initial pairing/root shell. Rooting may initially expose an unauthenticated root Telnet service; secure it promptly and do not forward it through your router.
- A Linux/macOS administrator workstation with Python 3.9+ and OpenSSH. The scripts use the Python standard library. The TV needs Python 3, the tested LG settings API, systemd, working IPv4 iptables, and the expected interface layout.
- Stable private IPv4 addresses for both TV and workstation. Use router DHCP reservations. **An administrator-address change can break SSH replies under this firewall.**
- Read the rollback section before applying changes. Do not assume Homebrew apps or exploits support every LG model.

## 1. Root and install Homebrew Channel

First clone this repository and enter its directory. A private GitHub repository requires access from its owner. Run subsequent commands from the repository root unless stated otherwise.

SlopBro is the exploit used in this case. Its payload installs Homebrew Channel and root persistence; it does not itself apply this project's privacy controls. Follow the [upstream project](https://github.com/throwaway96/slopbro) and [webOS Homebrew rooting guide](https://www.webosbrew.org/rooting/) for current compatibility information before attempting it.

The exact upstream revision used here was:

```sh
mkdir -p .private
chmod 700 .private
git clone https://github.com/throwaway96/slopbro.git .private/slopbro
git -C .private/slopbro checkout da374e5f10eff26b7df323ef0c2bc8470b142501
python3 .private/slopbro/slopbro.py --help
```

For this webOS 10 TV, the invocation followed this form, using **your actual private LAN addresses**:

```sh
python3 scripts/run-slopbro.py --host TV_IP --admin-ip TV_ADMIN_WORKSTATION_IP --webos-version 10
```

Approve pairing on the TV, follow the success/restart instructions, then verify root (`id -u` must report `0`). A success toast alone is insufficient verification. Do not accept optional agreements just to use HDMI. An agreement-refresh restart is different from installing new firmware; keep automatic firmware updates off while preserving this root method.

The original run used the official [Homebrew Channel 0.7.3 release](https://github.com/webosbrew/webos-homebrew-channel/releases/tag/v0.7.3). The downloaded IPK had SHA-256:

```text
d10bf3c753551d7c72fb7a92b20fcd2317e502a220ac668ba8e76f6ea78b363c
```

This repository does not vendor the exploit, package, or LG firmware files. A pinned exploit revision does not necessarily pin remote assets it downloads. Inspect upstream's asset-source options and verify any selected package yourself; do not apply the checksum above to a different release.

**Troubleshooting encountered in the original run:** the workstation firewall blocked the TV's inbound connection to SlopBro's temporary HTTP server. Only the TV's address was allowed to the chosen port, and that temporary exception was removed afterward. A browser idle preconnection also stalled the single-threaded server; a local `ThreadingHTTPServer` wrapper and a refreshed overlay launch resolved it. These are recorded as troubleshooting observations, not a required blanket firewall change. Never disable the workstation firewall globally or use insecure TLS merely to make a download succeed.

The included adapter reproduces the threaded-server fix without changing the upstream payload. It requires the clean pinned revision, binds only to the supplied workstation address, uses TCP 44767 by default, and refuses to silently switch ports. Permit inbound TCP to that port **only from your TV's address** using your workstation's firewall tools, if needed; remove that exception when done. Firewall syntax varies by operating system. Pairing still requires confirmation on the TV. If a previously launched overlay is stale, exit it and rerun the attempt rather than accepting an apparent success without a subsequent root check. The adapter itself has not been used to repeat the exploit on an additional TV; it packages the server adjustment used in the original session.

## 2. Configure a dedicated SSH key

From the repository root, replace the example addresses with your TV and workstation addresses:

```sh
python3 lgprivacy.py init --host 192.168.50.20 --admin-ip 192.168.50.10
python3 lgprivacy.py bootstrap-commands
```

`init` creates a dedicated, unencrypted SSH key for unattended local maintenance. It and the configuration are stored in `.private/`, with restrictive permissions. Protect your workstation and this directory. No configuration or credentials are shared with other users of this repository.

`bootstrap-commands` prints commands containing **only your public key**. Paste those commands, one line at a time, into an existing root shell on the TV. With the original Homebrew installation that was a local Telnet root shell; use SSH if you already have it. Do not copy anyone else's key, set a shared password, or paste a private key into the TV. If an SSH daemon already occupies port 22, leave it running and try the new key before replacing anything.

Establish trust for the TV's SSH host key:

```sh
python3 lgprivacy.py trust-host
python3 lgprivacy.py preflight
```

Check the host fingerprint using your trusted root-shell/bootstrap session when available. Do not ignore a changed host-key warning. `trust-host` performs an interactive first connection; subsequent operations require the saved host identity and do not silently accept changes.

The preflight checks root, SSH client address, webOS version, required tools, and interface names. It makes two public TCP connection probes, which may succeed before the firewall is installed; this is expected.

## 3. Apply and verify

This is designed for **HDMI-only** use and deliberately declines **all** LG agreements, including Terms/Privacy. Read the changes table before running it.

```sh
python3 lgprivacy.py install --disable-channels
python3 lgprivacy.py verify --channels
```

Omit `--disable-channels` if you want to leave that backend alone. Omitting it on a subsequent install does not undo a previous service block; use `restore-channels` for that. `--allow-untested` only bypasses the version gate after you have manually reviewed compatibility; it is not an automatic port to other firmware.

The installer:

1. Checks prerequisites and rejects unrelated OUTPUT firewall rules.
2. Saves authoritative consent/settings and an inspection report under `.private/backup-*/`.
3. Backs up overwritten startup files and authorized keys on the TV under `/var/lib/webosbrew/lg-owner-backup/install-*/`.
4. Installs key-only SSH startup behavior, verifies a fresh key connection, then stops Telnet.
5. Changes settings through LG's live API and reads back the consent state.
6. Installs the outbound firewall and optional LG Channels service block, then verifies the result.

It is not an atomic transaction: a later failure can leave earlier changes applied. It prints errors and keeps backups. Inspect the private reports and use the targeted rollback commands rather than repeatedly running the installer blindly.

Restart the TV when convenient. A full restart matters; remote power-off with Quick Start can merely suspend the TV. Open an authenticated root shell with `python3 lgprivacy.py shell`, use `sync; /sbin/reboot`, then wait for SSH to return. After the startup hooks finish:

```sh
python3 lgprivacy.py verify --channels
```

If a check fails during startup, allow initialization to finish and check once more. Inspect failures that persist. **Do not treat the debug-upload flag as successfully disabled after reboot:** the verifier reports its known reset separately. Root, consent, the other selected preferences, firewall rules, SSH/Telnet state, and optional LG Channels service state must pass.

For the strongest privacy, disconnect the TV's Ethernet and disable Wi-Fi after maintenance. Reconnect temporarily when you need SSH. Reserve the addresses so the firewall still permits maintenance after reconnecting.

## LG Channels prompt: what we found

The C2 repeatedly offered to set up LG Channels even with `channelplus` and `channelplusPopup` both off. Logs identified the `channelMapEmptyPopup` path. Inspection of the installed UI code showed that this path displayed the invitation despite an existing dismissal-history record.

The optional fix masks `/etc/systemd/system/dmost.service` with a bind mount from `/dev/null`, reloads systemd, and stops it. The underlying firmware file is untouched. The invitation normally depends on that backend reporting a supported country. Service state was verified as `masked`, `inactive`, `MainPID=0` after startup on the C2; **that is not proof that no invitation can ever appear before the hook runs**. Report a recurring prompt rather than assuming every Yes/No dialog is the same invitation.

LG also documents an official Disable LG Channels setting under the app's MY → Settings menu on newer sets. In this case the ordinary off settings were already insufficient. See [LG's instructions](https://www.lg.com/us/support/help-library/lg-tv-how-do-i-watch-lg-channels--20155049524788).

## Rollback and recovery

Keep key-based SSH available. These commands do not require rerunning SlopBro:

```sh
# Restore outbound network access now and prevent its hook from reapplying.
python3 lgprivacy.py restore-network

# Restore only the LG Channels backend.
python3 lgprivacy.py restore-channels

# Restore the backed-up option/general preferences, keeping agreements declined.
python3 lgprivacy.py restore-settings .private/backup-TIMESTAMP/settings.json
```

Restoring network access enables IPv6 on the known external interfaces; it is the inverse of this project's restriction, not a byte-for-byte restoration of every possible prior network configuration. Restoring Channels does not accept agreements or lift the firewall. To reapply restrictions, run `install` with the desired options again.

Restoring previous agreement acceptance can opt you back into collection. If deliberately desired, add `--include-consents` to `restore-settings`. This action uses LG's API and creates a fresh backup first. Never restore consent by copying `/var/luna/preferences/eula` alone: it is a cache.

For manual TV-side recovery through an existing owner root shell:

```sh
sh /var/lib/webosbrew/lg-owner/restore-network.sh
sh /var/lib/webosbrew/lg-owner/restore-lg-channels.sh
```

These create opt-out markers for the corresponding startup hooks:

- `/var/luna/preferences/lg_owner_network_privacy_off`
- `/var/luna/preferences/lg_owner_channels_enabled`

If your workstation's address changes, first try restoring its reserved address so SSH replies work again. If SSH is otherwise unavailable, use the recovery facilities documented for your Homebrew installation and firmware; this project has no guaranteed remote recovery from every failure. Do not factory-reset or flash partitions as a routine troubleshooting step.

To remove this project's hooks completely, first run the relevant rollback commands, then remove **only** `00-network-privacy`, `10-owner-ssh`, and `20-disable-lg-channels` from `/var/lib/webosbrew/init.d/` using an authenticated root shell. Removing `10-owner-ssh` removes the enforcement of password-disabled SSH at subsequent boot; review Homebrew's SSH settings before doing so. Homebrew itself and firmware-update blocking are separate and are not uninstalled by these rollback commands.

## More things root enables

SlopBro establishes persistent administrator access and installs Homebrew Channel. The broader ecosystem includes:

- **Remote-button remapping:** disable branded shortcut buttons or assign commands with [LG Input Hook](https://repo.webosbrew.org/apps/org.webosbrew.inputhook/).
- **Ambient backlighting:** [PicCap](https://repo.webosbrew.org/apps/org.webosbrew.piccap/) and Hyperion/HyperHDR can drive synchronized LEDs, including from HDMI content on supported configurations. Hardware/backend compatibility needs checking.
- **Custom screensavers:** replace webOS screensaver behavior with compatible Homebrew add-ons.
- **Media and games:** Kodi, Jellyfin, Moonlight game streaming, RetroArch, and a YouTube client with ad blocking/SponsorBlock are listed in the [Homebrew repository](https://repo.webosbrew.org/). Some apps also work without root through Developer Mode.
- **Administration:** SSH, persistent scripts, service control, settings backups and firewall policies, as demonstrated here.

These are ecosystem capabilities, not add-ons tested or installed by this project. Networked apps would require carefully chosen firewall exceptions. For an Apple TV owner, remote remapping and HDMI ambient lighting are likely more relevant than adding another streaming platform.

## Research and case notes

The motivation was LG viewing-data collection, including ACR associated with external HDMI content. Turning off only personalized advertisements is not the same as preventing all uploads.

- [RTINGS: smart-TV data privacy research](https://www.rtings.com/tv/learn/research/smart-tv-data-privacy) discusses observed network behavior and the limits of encrypted-traffic analysis.
- [Texas Attorney General: May 2026 LG agreement](https://www.texasattorneygeneral.gov/news/releases/attorney-general-ken-paxton-secures-major-agreement-lg-protect-texans-privacy-and-stop-data-being) describes privacy/consent commitments. It does not establish which settings are currently effective on every TV.
- [Gamers Nexus: September 2026 LG investigation](https://www.youtube.com/watch?v=6IFVTcM28KA) provided contemporary context. Exploit demonstrations are not evidence that this particular stock C2 continually uploaded microphone recordings.
- [Level1Techs guide](https://forum.level1techs.com/t/lg-tv-block-mini-how-to/255178) informed exploration, but some procedures required adjustment on this firmware.

See [the sanitized case notes](docs/case-study.md) for working and unsuccessful approaches. No user credentials, MAC addresses, serial numbers, private LAN addresses, raw consent documents, logs, or LG proprietary source are included.

## Development and sharing

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile lgprivacy.py tv/inspect.py tv/install-files.py
git add .gitignore README.md lgprivacy.py tv tests scripts docs
python3 scripts/check-staged-secrets.py
git diff --cached --stat
```

Review the actual staged diff before committing. `.private/` is ignored, but Git ignore rules are not encryption and do not protect files that someone explicitly force-adds. The included scanner inspects the index and rejects common key/token patterns and private artifact paths; it supplements manual review.

Share this Git repository or a Git-generated source archive. **Do not zip the entire working directory:** that can include `.private/`. A private GitHub repository also requires explicitly inviting your friends as collaborators before they can clone it. Never share your device key with them; each person generates their own.
