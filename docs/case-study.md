# Sanitized session record

This records the original September 8, 2026 C2 session separately from the reusable installer. The user's goal was an HDMI-only display for Apple TV with LG collection/upload features disabled as far as practical.

## Identification and root

The TV's own information screens identified OLED55C2AUA, firmware 33.31.24, webOS 10.3.0-2504 (webOS 25). Automatic updates were off. Owner-authorized network pairing succeeded after retry. The TV exposed overlay applications usable by the SlopBro revision pinned in the README.

The rooting HTTP server needed a narrowly scoped temporary workstation-firewall exception. An idle browser preconnection stalled the stock single-threaded HTTP server; a local threaded wrapper and refreshed overlay launch resolved that. Exploit payload code was not modified. All required assets were served, the TV displayed success, and UID 0 was confirmed after restart. The temporary firewall exception was removed.

The Homebrew 0.7.3 package checksum was checked. A dedicated owner SSH key was installed, a new root SSH session was verified, password login was disabled through a persistent hook, and Telnet was stopped/disabled. No signed firmware partition was overwritten.

## Consent and privacy preferences

Backing out of an agreement screen did not revoke the previously stored agreements. The original TV retained several accepted documents and an allowed-network flag.

A guide-inspired direct edit of `/var/luna/preferences/eula`, including an ACR marker, did not persist after reboot. That method was abandoned. Killing/restarting the consent service did not make cache-file edits authoritative. The historical experiment is retained only in the original owner's ignored private archive.

The working method used `com.webos.settingsservice` with **uncategorized** `eulaStatus`, `eulaInfo`, and `eulaInfoNetwork` keys. Asking for `category: eula` did not address the real database values on this firmware. `luna-send` needed an SSH pseudo-terminal to wait reliably for responses. The successful procedure backed up values, preserved metadata, declined all existing consent flags/documents, and read the state back through the same API.

After restart, no agreements were accepted and all `*Allowed` flags were false. Viewing-history, advertising and selected voice/privacy preferences persisted. `dbgLogUpload` returned to true; this is explicitly reported rather than hidden or counted as a successful persistent opt-out.

## Network restriction

IPv4 iptables worked on this C2. The expected IPv6 iptables support was unavailable, so the procedure disabled external-interface IPv6 instead. The outbound policy retained loopback, DHCP, and SSH replies to the administrator's reserved IPv4 address. Other output was dropped.

After restart, firewall counters increased, an IPv4 public TCP/443 probe timed out, and an IPv6 probe returned network unreachable. SSH remained available. These observations establish the configured post-startup restriction, not the absence of every possible pre-hook packet. Physical disconnection was recommended for HDMI-only use.

Homebrew's own startup code also masks certain crash/telemetry spool paths and provides update-host blocking. Those are upstream Homebrew behaviors, not newly written code in this repository.

The kernel boot ID did not change during the observed LG restarts even though uptime reset. Verification therefore used uptime and service/settings checks rather than assuming a new boot ID.

## LG Channels invitation

The user reported recurring invitations requiring No. Both normal Channels-related off settings were already off. TV logs identified `channelMapEmptyPopup`; local UI-source inspection showed that this path calls the invitation display function without waiting for its stored dismissal-history result. No LG source is redistributed here.

The dedicated `dmost.service` backend was reversibly masked and stopped with a Homebrew startup hook. After reboot it reached `LoadState=masked`, `ActiveState=inactive`, `MainPID=0`. An early check briefly saw `masked` with a running PID while startup was still completing. The fix should suppress backend-dependent invitations once applied, but recurring-prompt behavior still requires observation on the actual display and may have an early-boot gap. Do not market it as a proven universal popup remover.

## Reproducible project and private archive

The original session directory was moved under this project's ignored `.private/` directory. A local compatibility symlink preserves old maintenance commands. Raw photos, downloaded packages, the upstream exploit checkout, pairing credentials, keys, consent backups, logs and captured LG source are not part of Git.

The original user also requested a workstation Codex Full Access default. That separate local configuration change was completed and backed up. It is not needed to run these scripts and is deliberately not reproduced as part of a TV-privacy installation.

The reusable code adds input validation, preflight checks, private backups, explicit rollback commands and failure-reporting around the procedures that worked. The privacy installer does not perform exploitation; the separate optional server adapter invokes the upstream exploit only when explicitly run. Neither claims untested firmware support.

The reusable installer's `install --disable-channels` command was subsequently executed on the same rooted C2. Installation and verification passed, including a fresh root SSH connection, authoritative consent readback, the selected privacy settings, exact expected firewall rules, blocked public IPv4/IPv6 probes, and a masked/inactive LG Channels backend. Rooting was not repeated. Automated local tests exercise consent-schema rejection, preservation of metadata, address validation, SSH-return-address mismatch rejection, and staged-secret detection. Validation on this one C2 does not substitute for testing another model.
