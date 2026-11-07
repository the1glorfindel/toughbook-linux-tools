#!/usr/bin/env bash
set -euo pipefail

name=panasonic-hbtn
version=0.1.0
udev_rule=/etc/udev/rules.d/70-panasonic-hbtn.rules

if [[ ${EUID} -ne 0 ]]; then
	printf 'Run with sudo: %s\n' "$0" >&2
	exit 1
fi

if command -v dkms >/dev/null && dkms status -m "$name" -v "$version" 2>/dev/null | grep -q .; then
	dkms remove -m "$name" -v "$version" --all
fi
rm -rf "/usr/src/${name}-${version}"
rm -f "$udev_rule"
udevadm control --reload-rules 2>/dev/null || true
printf 'Removed DKMS registration and source. An already loaded module remains loaded until reboot or manual unload.\n'
