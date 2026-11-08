#!/usr/bin/env bash
set -euo pipefail

source /etc/os-release
[[ ${ID:-} == ubuntu || " ${ID_LIKE:-} " == *' ubuntu '* ]] || {
    printf 'This setup script is for Ubuntu.\n' >&2
    exit 1
}
[[ ${EUID} -ne 0 ]] || { printf 'Run as your desktop user; the script uses sudo for packages.\n' >&2; exit 1; }
cd "$(dirname "$0")/.."

sudo apt-get update
packages=(python3 python3-venv python3-pip python3-dbus python3-gi python3-tk
          xwayland pipewire-bin wireplumber pulseaudio-utils alsa-utils udev
          xdg-desktop-portal pkexec build-essential dkms mokutil openssl)

desktop=${XDG_CURRENT_DESKTOP:-}
if [[ ${desktop,,} == *kde* || ${desktop,,} == *plasma* ]]; then
    packages+=(xdg-desktop-portal-kde)
    if apt-cache show libkscreen-bin >/dev/null 2>&1; then
        packages+=(libkscreen-bin)
    else
        packages+=(libkf5screen-bin)
    fi
else
    packages+=(xdg-desktop-portal-gnome)
fi

headers="linux-headers-$(uname -r)"
if apt-cache show "$headers" >/dev/null 2>&1; then
    packages+=("$headers")
else
    printf 'Matching headers for %s are unavailable in APT; the optional button driver cannot build yet.\n' "$(uname -r)" >&2
fi
system_pyside=false
if apt-cache show python3-pyside6.qtwidgets >/dev/null 2>&1; then
    packages+=(python3-pyside6.qtwidgets)
    system_pyside=true
    if apt-cache show qt6-wayland >/dev/null 2>&1; then
        packages+=(qt6-wayland)
    fi
fi
sudo apt-get install -y "${packages[@]}"

if $system_pyside; then
    python3 -c 'import PySide6, dbus, gi'
    python3 toughbook-tools.py --install
else
    # Ubuntu 24.04 lacks a system PySide6 package. Keep Qt in a persistent venv
    # while exposing distribution dbus-python and GI packages to it.
    venv="${XDG_DATA_HOME:-$HOME/.local/share}/toughbook-tools-python"
    mkdir -p "$(dirname "$venv")"
    python3 -m venv --system-site-packages "$venv"
    "$venv/bin/python" -m pip install --upgrade PySide6
    "$venv/bin/python" -c 'import PySide6, dbus, gi'
    "$venv/bin/python" toughbook-tools.py --install
fi
printf 'Installed Toughbook Tools. Launch it from the app menu.\n'
