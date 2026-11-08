"""Distribution-specific package commands for the optional kernel driver."""
from pathlib import Path
import os
import shutil

from .common import ToolError


def distro_id(path=Path('/etc/os-release')):
    values = {}
    for line in path.read_text().splitlines():
        if '=' in line and not line.startswith('#'):
            key, value = line.split('=', 1)
            values[key] = value.strip().strip('"')
    ids = [values.get('ID', ''), *values.get('ID_LIKE', '').split()]
    if 'ubuntu' in ids or 'debian' in ids:
        return 'ubuntu'
    if 'fedora' in ids or 'rhel' in ids:
        return 'fedora'
    raise ToolError('Automatic prerequisite installation supports Ubuntu/Debian and Fedora only.')


def driver_packages(release=None, distro=None):
    release = release or os.uname().release
    distro = distro or distro_id()
    if distro == 'ubuntu':
        return ['build-essential', f'linux-headers-{release}', 'dkms', 'mokutil', 'openssl']
    if distro == 'fedora':
        return ['make', 'gcc', f'kernel-devel-{release}', 'dkms', 'mokutil', 'openssl']
    raise ToolError(f'Unsupported package family: {distro}')


def driver_install_command(release=None, distro=None):
    distro = distro or distro_id()
    executable = shutil.which('apt-get' if distro == 'ubuntu' else 'dnf')
    if not executable:
        raise ToolError(f'Package manager for {distro} was not found.')
    return [executable, 'install', '-y', *driver_packages(release, distro)]
