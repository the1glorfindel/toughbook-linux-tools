#!/usr/bin/env bash
set -euo pipefail

name=panasonic-hbtn
version=0.1.0
target=/usr/src/${name}-${version}
udev_rule=/etc/udev/rules.d/70-panasonic-hbtn.rules

if [[ ${EUID} -ne 0 ]]; then
	printf 'Run with sudo: %s\n' "$0" >&2
	exit 1
fi

for program in make gcc modinfo udevadm; do
    command -v "$program" >/dev/null || { printf 'Missing build tool: %s\n' "$program" >&2; exit 1; }
done
[[ -d /usr/src/kernels/$(uname -r) ]] || { printf 'Install matching kernel-devel first.\n' >&2; exit 1; }
if [[ -e $target || -e $udev_rule ]]; then
    printf 'A source directory or udev rule already exists. Inspect it before replacing anything.\n' >&2
    exit 1
fi

if ! command -v dkms >/dev/null; then
	printf 'DKMS is required. Install the Fedora dkms package and kernel-devel for the running kernel.\n' >&2
	exit 1
fi

for device in /sys/bus/acpi/devices/MAT001F:*; do
	[[ -e $device ]] || continue
	if [[ -L $device/driver ]]; then
		bound=$(basename "$(readlink -f "$device/driver")")
		if [[ $bound != "$name" ]]; then
			printf '%s is already bound to %s; refusing to replace or unbind it.\n' "${device##*/}" "$bound" >&2
			exit 1
		fi
	fi
done

if modinfo panasonic_hbtn >/dev/null 2>&1 || modinfo panasonic-hbtn >/dev/null 2>&1; then
	printf 'A panasonic-hbtn module is already available; inspect it before proceeding.\n' >&2
	exit 1
fi

if [[ -d /sys/firmware/efi ]]; then
    command -v mokutil >/dev/null || { printf 'Install mokutil to check Secure Boot before installation.\n' >&2; exit 1; }
    sb_state=$(mokutil --sb-state) || { printf 'Cannot determine Secure Boot state; inspect firmware before proceeding.\n' >&2; exit 1; }
    printf '%s\n' "$sb_state"
    if [[ $sb_state == *enabled* ]]; then
        printf 'Secure Boot enabled: DKMS module signing and MOK enrollment are required; see README.md.\n'
    fi
else
    printf 'Legacy boot: EFI Secure Boot is not active.\n'
fi

cleanup() {
    dkms remove -m "$name" -v "$version" --all >/dev/null 2>&1 || true
    rm -rf "$target"
    rm -f "$udev_rule"
    udevadm control --reload-rules || true
}
trap cleanup ERR
install -d "$target"
install -m 0644 "$(dirname "$0")/panasonic-hbtn.c" "$(dirname "$0")/hbtn-decode.h" "$(dirname "$0")/Makefile" "$(dirname "$0")/dkms.conf" "$(dirname "$0")/COPYING" "$target/"
dkms add -m "$name" -v "$version"
dkms build -m "$name" -v "$version" -k "$(uname -r)"
install -D -m 0644 "$(dirname "$0")/70-panasonic-hbtn.rules" "$udev_rule"
udevadm control --reload-rules
dkms install -m "$name" -v "$version" -k "$(uname -r)"
# A DKMS post-transaction hook may have caused modalias discovery already.
# Refresh only this driver's input nodes, never the ordinary keyboard.
for event in /sys/class/input/event*; do
    [[ -r $event/device/name ]] || continue
    [[ $(cat "$event/device/name") == "Panasonic CF-19 Tablet Buttons" ]] || continue
    [[ $(readlink -f "$event/device") == *'/MAT001F:'* ]] || continue
    udevadm trigger --action=add "$event"
done
udevadm settle
trap - ERR
printf 'Installed for kernel %s. No module load or device binding was requested.\n' "$(uname -r)"
