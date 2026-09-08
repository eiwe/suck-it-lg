#!/bin/sh
set -eu
touch /var/luna/preferences/lg_owner_channels_enabled
unit=/etc/systemd/system/dmost.service
if awk -v p="$unit" '$2 == p {found=1} END {exit !found}' /proc/mounts; then
    umount "$unit"
fi
systemctl daemon-reload
systemctl start dmost.service
echo 'LG Channels backend restored. Consent and network restrictions unchanged.'
