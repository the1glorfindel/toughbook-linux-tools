"""Install distribution dependencies and the per-user app. SPDX-License-Identifier: MIT"""
import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess

from . import distro
from .common import ToolError, desktop_user


ROOT = Path(__file__).resolve().parents[1]


def execute(argv):
    print('+ ' + shlex.join(map(str, argv)), flush=True)
    subprocess.run(list(map(str, argv)), check=True, cwd=ROOT)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--desktop', choices=('kde', 'gnome', 'generic'), help='Override desktop detection')
    parser.add_argument('--dry-run', action='store_true', help='Print a JSON plan without installing or changing files')
    parser.add_argument('--driver-prerequisites', action='store_true',
                        help='Also install build tools and running-kernel headers; never install/load the driver')
    args = parser.parse_args(argv)
    family = distro.distro_id()
    desktop = args.desktop or distro.desktop_id()
    if not args.dry_run:
        desktop_user()
        if not Path('/run/systemd/system').is_dir():
            raise ToolError('Automatic setup requires systemd; see docs/linux.md for scope and manual setup.')
        if not shutil.which('sudo'):
            raise ToolError('Install sudo and configure administrator access before running setup.')
        # Refresh before resolving APT candidates, including newly enabled repositories.
        if family == 'debian':
            execute(['sudo', 'apt-get', 'update'])
    packages, venv = distro.app_packages(family, desktop)
    if args.driver_prerequisites:
        packages = list(dict.fromkeys([*packages, *distro.driver_packages(distro=family)]))
    command = distro.install_command(packages, family)
    plan = {'family': family, 'desktop': desktop, 'command': command,
            'pyside6_virtualenv': venv, 'driver_prerequisites': args.driver_prerequisites}
    if args.dry_run:
        print(json.dumps(plan, indent=2))
        return 0
    if family == 'arch':
        print('Arch: use an up-to-date system (pacman -Syu). Setup does not refresh databases '
              'or upgrade the system; resolve conflicts in the package-manager prompt.', flush=True)
    execute(['sudo', *command])
    interpreter = Path('/usr/bin/python3')
    if venv:
        data = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share')
        environment = data / 'toughbook-tools-python'
        execute([interpreter, '-m', 'venv', '--system-site-packages', environment])
        interpreter = environment / 'bin/python'
        execute([interpreter, '-m', 'pip', 'install', '--upgrade', 'PySide6'])
    execute([interpreter, '-c', 'from PySide6 import QtCore, QtGui, QtWidgets; import dbus, gi; from gi.repository import Gio, GLib'])
    execute([interpreter, ROOT / 'toughbook-tools.py', '--install'])
    print('Installed Toughbook Tools. Launch it from the app menu. '
          'Audio requires an existing PipeWire/WirePlumber session; see docs/linux.md.')
    return 0
