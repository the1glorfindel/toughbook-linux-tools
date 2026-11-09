"""Cross-distribution package selection and setup orchestration."""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from toughbook import distro, setup
from toughbook.common import ToolError


class DistroTests(unittest.TestCase):
    def test_distribution_identity_and_derivatives(self):
        cases = [('debian', '', 'debian'), ('ubuntu', 'debian', 'debian'),
                 ('linuxmint', 'ubuntu debian', 'debian'), ('pop', 'ubuntu debian', 'debian'),
                 ('fedora', '', 'fedora'), ('nobara', 'fedora', 'fedora'),
                 ('arch', '', 'arch'), ('manjaro', 'arch', 'arch'),
                 ('endeavouros', 'arch', 'arch'), ('arch', 'debian', 'arch')]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'os-release'
            for identity, like, family in cases:
                with self.subTest(identity=identity):
                    path.write_text(f"# comment\nID='{identity}'\nID_LIKE=\"{like}\"\n")
                    self.assertEqual(distro.distro_id(path), family)
            for identity in ('opensuse', 'rhel', 'alpine'):
                path.write_text(f'ID={identity}\n')
                with self.assertRaises(ToolError):
                    distro.distro_id(path)

    def test_desktop_detection_and_explicit_rejection(self):
        for value, expected in [('ubuntu:GNOME', 'gnome'), ('KDE', 'kde'), ('plasma', 'kde')]:
            self.assertEqual(distro.desktop_id(value), expected)
        with self.assertRaises(ToolError):
            distro.desktop_id('XFCE')

    def test_debian_pyside_and_kde_package_fallback(self):
        packages, venv = distro.app_packages('debian', 'kde', available=lambda p: p == 'libkf5screen-bin')
        self.assertTrue(venv)
        self.assertIn('libkf5screen-bin', packages)
        self.assertNotIn('python3-pyside6.qtwidgets', packages)
        packages, venv = distro.app_packages('debian', 'kde', available=lambda p: True)
        self.assertFalse(venv)
        self.assertIn('python3-pyside6.qtwidgets', packages)
        self.assertIn('qt6-wayland', packages)
        self.assertIn('libkscreen-bin', packages)
        with self.assertRaises(ToolError):
            distro.app_packages('debian', 'kde', available=lambda p: False)

    def test_apt_requires_an_installable_candidate(self):
        for output, expected in [('  Candidate: 6.8.2\n', True),
                                 ('  Candidate: (none)\n', False), ('', False)]:
            with patch.object(distro, 'run', return_value=SimpleNamespace(stdout=output)) as run:
                self.assertEqual(distro.package_available('example'), expected)
                self.assertEqual(run.call_args.kwargs['env']['LC_ALL'], 'C')

    def test_each_family_has_desktop_backend_and_all_runtime_tools(self):
        for family in ('debian', 'fedora', 'arch'):
            for desktop in ('kde', 'gnome'):
                with self.subTest(family=family, desktop=desktop):
                    packages, venv = distro.app_packages(family, desktop, available=lambda p: True)
                    self.assertFalse(venv)
                    self.assertIn('xdg-desktop-portal-' + desktop, packages)
                    self.assertNotIn('xdg-desktop-portal-' + ('gnome' if desktop == 'kde' else 'kde'), packages)
                    self.assertIn('alsa-utils', packages)
                    self.assertIn('wireplumber', packages)
                    self.assertNotIn('dkms', packages)
        arch, _ = distro.app_packages('arch', 'kde')
        for package in ('python-dbus', 'python-gobject', 'pipewire-audio', 'alsa-card-profiles', 'libpulse', 'libkscreen'):
            self.assertIn(package, arch)
        fedora, _ = distro.app_packages('fedora', 'kde')
        for package in ('python3-tkinter', 'xorg-x11-server-Xwayland', 'polkit', 'pipewire-libs', 'libkscreen'):
            self.assertIn(package, fedora)

    def test_driver_packages_match_running_kernel(self):
        self.assertIn('linux-headers-test-kernel', distro.driver_packages('test-kernel', 'debian'))
        self.assertIn('kernel-devel-test-kernel', distro.driver_packages('test-kernel', 'fedora'))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'test-kernel').mkdir()
            for kernel in ('linux', 'linux-lts', 'linux-zen', 'linux-hardened', 'linux-custom'):
                (root / 'test-kernel/pkgbase').write_text(kernel + '\n')
                self.assertIn(kernel + '-headers', distro.driver_packages('test-kernel', 'arch', root))
            (root / 'test-kernel/pkgbase').write_text('../invalid')
            with self.assertRaises(ToolError):
                distro.driver_packages('test-kernel', 'arch', root)
            with self.assertRaises(ToolError):
                distro.driver_packages('missing', 'arch', root)

    def test_native_install_commands_and_missing_manager(self):
        for family, manager, options in [('debian', 'apt-get', ['install', '-y']),
                                         ('fedora', 'dnf', ['install', '-y']),
                                         ('arch', 'pacman', ['-S', '--needed'])]:
            with patch.object(distro.shutil, 'which', side_effect=lambda p: '/usr/bin/' + p):
                self.assertEqual(distro.install_command(['example'], family),
                                 ['/usr/bin/' + manager, *options, 'example'])
                command = distro.driver_install_command('test', family) if family != 'arch' else None
                if command:
                    self.assertIn('dkms', command)
        with patch.object(distro.shutil, 'which', return_value=None), self.assertRaises(ToolError):
            distro.install_command(['example'], 'arch')
        with self.assertRaises(ToolError):
            distro.install_command([], 'unknown')

    def test_gui_pacman_does_not_wait_for_terminal_confirmation(self):
        with patch.object(distro.shutil, 'which', return_value='/usr/bin/pacman'), \
             patch.object(distro, 'driver_packages', return_value=['dkms']):
            self.assertEqual(distro.driver_install_command(distro='arch'),
                             ['/usr/bin/pacman', '-S', '--needed', '--noconfirm', 'dkms'])


class SetupTests(unittest.TestCase):
    def test_dry_run_never_installs_or_changes_files(self):
        for family in ('debian', 'fedora', 'arch'):
            with self.subTest(family=family), patch.object(distro, 'distro_id', return_value=family), \
                 patch.object(distro, 'package_available', return_value=True), \
                 patch.object(distro.shutil, 'which', side_effect=lambda p: '/usr/bin/' + p), \
                 patch.object(setup, 'execute') as execute, redirect_stdout(io.StringIO()) as output:
                self.assertEqual(setup.main(['--dry-run', '--desktop', 'kde']), 0)
                plan = json.loads(output.getvalue())
                self.assertEqual(plan['family'], family)
                self.assertNotIn('dkms', plan['command'])
                execute.assert_not_called()

    def test_setup_uses_system_python_or_persistent_venv_and_never_loads_driver(self):
        for fallback in (False, True):
            with self.subTest(fallback=fallback), tempfile.TemporaryDirectory() as folder, \
                 patch.dict(os.environ, {'XDG_DATA_HOME': folder}), \
                 patch.object(distro, 'distro_id', return_value='debian'), \
                 patch.object(distro, 'app_packages', return_value=(['python3'], fallback)), \
                 patch.object(distro, 'install_command', return_value=['apt-get', 'install', '-y', 'python3']), \
                 patch.object(setup, 'desktop_user'), \
                 patch.object(setup.Path, 'is_dir', return_value=True), \
                 patch.object(setup.shutil, 'which', return_value='/usr/bin/sudo'), \
                 patch.object(setup, 'execute') as execute, redirect_stdout(io.StringIO()):
                setup.main(['--desktop', 'gnome'])
                calls = [list(map(str, c.args[0])) for c in execute.call_args_list]
                self.assertEqual(calls[0], ['sudo', 'apt-get', 'update'])
                python = str(Path(folder) / 'toughbook-tools-python/bin/python') if fallback else '/usr/bin/python3'
                self.assertEqual(calls[-1], [python, str(setup.ROOT / 'toughbook-tools.py'), '--install'])
                self.assertFalse(any('modprobe' in c or 'driver/install.sh' in c for c in calls))
                self.assertEqual(any('pip' in c for c in calls), fallback)

    def test_driver_prerequisites_are_opt_in(self):
        with patch.object(distro, 'distro_id', return_value='fedora'), \
             patch.object(distro.shutil, 'which', side_effect=lambda p: '/usr/bin/' + p), \
             redirect_stdout(io.StringIO()) as output:
            setup.main(['--dry-run', '--desktop', 'gnome', '--driver-prerequisites'])
        self.assertIn('dkms', json.loads(output.getvalue())['command'])


if __name__ == '__main__':
    unittest.main()
