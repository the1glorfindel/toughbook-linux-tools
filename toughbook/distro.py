"""Package selection for Debian, Fedora and Arch Linux families. SPDX-License-Identifier: MIT"""
from pathlib import Path
import os
import re
import shlex
import shutil

from .common import ToolError, run


def distro_id(path=Path('/etc/os-release')):
    values = {}
    for line in path.read_text().splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            key, value = line.split('=', 1)
            parts = shlex.split(value, comments=True)
            values[key.strip()] = parts[0] if parts else ''
    # The distribution's own ID takes precedence over compatibility hints.
    for identity in [values.get('ID', ''), *values.get('ID_LIKE', '').split()]:
        if identity in ('debian', 'ubuntu'):
            return 'debian'
        if identity in ('fedora', 'arch'):
            return identity
    raise ToolError('Automatic setup supports Debian-based, Fedora and Arch-based systems. '
                    'Other distributions need manual dependencies; see docs/linux.md.')


def family_name(distro):
    return {'debian': 'Debian / Ubuntu', 'ubuntu': 'Debian / Ubuntu',
            'fedora': 'Fedora', 'arch': 'Arch Linux'}.get(distro, distro)


def desktop_id(value=None):
    value = (value if value is not None else os.environ.get('XDG_CURRENT_DESKTOP', '')).lower()
    if 'kde' in value or 'plasma' in value:
        return 'kde'
    if 'gnome' in value:
        return 'gnome'
    return 'generic'


def package_available(package):
    """Use APT candidates, not apt-cache show (which also finds obsolete packages)."""
    output = run('apt-cache', 'policy', package, env={**os.environ, 'LC_ALL': 'C'}).stdout
    match = re.search(r'^\s*Candidate:\s*(\S+)', output, re.MULTILINE)
    return bool(match and match[1] != '(none)')


def app_packages(distro, desktop, available=None):
    """Return (packages, needs_PySide_venv); no installation or session changes."""
    if desktop not in ('kde', 'gnome', 'generic'):
        raise ToolError('Choose kde, gnome or generic dependencies.')
    portal = 'xdg-desktop-portal-' + (desktop if desktop != 'generic' else 'gtk')
    if distro in ('debian', 'ubuntu'):
        available = available or package_available
        packages = ['python3', 'python3-venv', 'python3-pip', 'python3-dbus', 'python3-gi',
                    'python3-tk', 'xwayland', 'xinput', 'xserver-xorg-input-libinput', 'x11-xserver-utils', 'pipewire-bin', 'wireplumber', 'pulseaudio-utils',
                    'alsa-utils', 'udev', 'systemd', 'dbus-user-session', 'libglib2.0-bin', 'xdg-desktop-portal', portal,
                    'pkexec', 'sudo', 'kmod']
        venv = not available('python3-pyside6.qtwidgets')
        if not venv:
            packages += ['python3-pyside6.qtwidgets', 'qt6-wayland']
        else:
            # Wheels bundle Qt, but not its native XCB/graphics dependencies.
            # Minimal X11 desktops need these even when no distro Qt is installed.
            packages += ['libegl1', 'libgl1', 'libfontconfig1', 'libdbus-1-3',
                         'libx11-xcb1', 'libxkbcommon-x11-0', 'libxcb-cursor0',
                         'libxcb-icccm4', 'libxcb-image0', 'libxcb-keysyms1',
                         'libxcb-render-util0', 'libxcb-xinerama0', 'libxcb-xkb1',
                         'libxcb-randr0', 'libxcb-shape0', 'libxcb-shm0',
                         'libxcb-sync1', 'libxcb-xfixes0']
        if desktop == 'kde':
            screen = next((p for p in ('libkscreen-bin', 'libkf5screen-bin') if available(p)), None)
            if screen is None:
                raise ToolError('No KDE screen helper package is available. Enable the distribution '
                                'repository providing kscreen-doctor and retry.')
            packages.append(screen)
        if desktop == 'generic':
            packages.append('wlr-randr')
        return packages, venv
    if distro == 'fedora':
        packages = ['python3', 'python3-pyside6', 'qt6-qtwayland', 'python3-dbus',
                    'python3-gobject', 'python3-tkinter', 'xorg-x11-server-Xwayland', 'xinput', 'xorg-x11-drv-libinput', 'xrandr',
                    'pipewire-utils', 'pipewire-libs', 'wireplumber', 'pulseaudio-utils',
                    'alsa-utils', 'systemd', 'systemd-udev', 'dbus', 'glib2', 'polkit', 'sudo', 'kmod',
                    'xdg-desktop-portal', portal]
    elif distro == 'arch':
        packages = ['python', 'pyside6', 'qt6-wayland', 'python-dbus', 'python-gobject',
                    'tk', 'xorg-xwayland', 'xorg-xinput', 'xorg-xrandr', 'pipewire', 'pipewire-audio', 'alsa-card-profiles',
                    'wireplumber', 'libpulse', 'alsa-utils', 'systemd', 'dbus', 'glib2', 'polkit',
                    'sudo', 'kmod', 'xdg-desktop-portal', portal]
    else:
        raise ToolError(f'Unsupported package family: {distro}')
    if desktop == 'kde':
        packages.append('libkscreen')
    if desktop == 'generic':
        packages.append('wlr-randr')
    return packages, False


def install_command(packages, distro, noninteractive=False):
    managers = {'debian': 'apt-get', 'ubuntu': 'apt-get', 'fedora': 'dnf', 'arch': 'pacman'}
    if distro not in managers:
        raise ToolError(f'Unsupported package family: {distro}')
    executable = shutil.which(managers[distro])
    if not executable:
        raise ToolError(f'Package manager {managers[distro]} was not found.')
    # Never refresh Arch databases without a full upgrade, or hide conflicts.
    options = ['-S', '--needed'] if distro == 'arch' else ['install', '-y']
    if distro == 'arch' and noninteractive:
        options.append('--noconfirm')
    return [executable, *options, *packages]


def driver_packages(release=None, distro=None, modules=Path('/usr/lib/modules')):
    release = release or os.uname().release
    distro = distro or distro_id()
    if distro in ('debian', 'ubuntu'):
        return ['build-essential', f'linux-headers-{release}', 'dkms', 'mokutil', 'openssl', 'kmod', 'udev']
    if distro == 'fedora':
        return ['make', 'gcc', f'kernel-devel-{release}', 'dkms', 'mokutil', 'openssl', 'kmod', 'systemd-udev']
    if distro == 'arch':
        try:
            pkgbase = (modules / release / 'pkgbase').read_text().strip()
        except OSError as exc:
            raise ToolError('Cannot identify the running Arch kernel package. Install its matching '
                            'headers manually; see docs/linux.md.') from exc
        if not re.fullmatch(r'[a-z0-9][a-z0-9+_.-]*', pkgbase):
            raise ToolError('Invalid Arch kernel pkgbase; install matching headers manually.')
        return ['base-devel', f'{pkgbase}-headers', 'dkms', 'mokutil', 'openssl', 'kmod', 'systemd']
    raise ToolError(f'Unsupported package family: {distro}')


def driver_install_command(release=None, distro=None):
    distro = distro or distro_id()
    # GUI QProcess has no terminal for Pacman's confirmation prompt. The page
    # already shows the complete package list and asks for confirmation.
    return install_command(driver_packages(release, distro), distro, noninteractive=True)
