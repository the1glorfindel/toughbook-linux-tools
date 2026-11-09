"""Portable commands, resources, installed helpers and host environment isolation."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from toughbook import runtime


class RuntimeTests(unittest.TestCase):
    def test_source_and_frozen_commands_use_the_correct_interpreter(self):
        with patch.object(runtime, 'frozen', return_value=False):
            self.assertEqual(runtime.command('toughbook-buttons.py', '--status', root='/tmp/installed'),
                             [sys.executable, '/tmp/installed/toughbook-buttons.py', '--status'])
        with patch.object(runtime, 'frozen', return_value=True):
            self.assertEqual(runtime.command('toughbook-buttons.py', '--status', root='/tmp/installed'),
                             ['/tmp/installed/toughbook-tools', '--tool', 'buttons', '--status'])
            self.assertEqual(runtime.command('calibrate-screen.py', '--activate', root='/tmp/installed')[1:],
                             ['--tool', 'screen', '--activate'])

    def test_host_commands_do_not_inherit_frozen_library_or_plugin_paths(self):
        environment = {'PATH': '/usr/bin', 'LD_LIBRARY_PATH': '/bundle/_internal',
                       'LD_LIBRARY_PATH_ORIG': '/original/lib', 'QT_PLUGIN_PATH': '/bundle/plugins',
                       'GI_TYPELIB_PATH': '/bundle/typelibs', 'PIPEWIRE_MODULE_DIR': '/bundle/pipewire',
                       '_PYI_ARCHIVE_FILE': '/bundle/toughbook-tools', 'DISPLAY': ':7'}
        with patch.object(runtime, 'frozen', return_value=True), patch.object(runtime, '_ORIGINAL', {}):
            cleaned = runtime.host_environment(environment)
        self.assertEqual(cleaned['LD_LIBRARY_PATH'], '/original/lib')
        self.assertEqual(cleaned['DISPLAY'], ':7')
        for name in ('QT_PLUGIN_PATH', 'GI_TYPELIB_PATH', 'PIPEWIRE_MODULE_DIR', '_PYI_ARCHIVE_FILE'):
            self.assertNotIn(name, cleaned)

    def test_bundled_clients_and_host_programs_use_separate_environments(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'bin').mkdir()
            (root/'bin/pactl').write_text('client')
            with patch.object(runtime, 'frozen', return_value=True), \
                 patch.object(runtime, 'resources', return_value=root), \
                 patch.object(runtime, '_ORIGINAL', {}), \
                 patch.dict(os.environ, {'LD_LIBRARY_PATH': '/bundle', 'DISPLAY': ':7'}, clear=True):
                argv, env = runtime.program_invocation(['pactl', 'info'])
                self.assertEqual(argv[0], str(root/'bin/pactl'))
                self.assertEqual(env['LD_LIBRARY_PATH'], '/bundle')
                argv, env = runtime.program_invocation(['systemctl', '--user', 'status'])
                self.assertEqual(argv[0], 'systemctl')
                self.assertNotIn('LD_LIBRARY_PATH', env)

    def test_runtime_initialization_preserves_custom_host_environment(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'alsa').mkdir()
            with patch.object(runtime, 'frozen', return_value=True), \
                 patch.object(runtime, 'resources', return_value=root), \
                 patch.object(runtime, '_ORIGINAL', {}), \
                 patch.dict(os.environ, {'PATH': '/usr/bin', 'ALSA_CONFIG_DIR': '/custom/alsa'}, clear=True):
                runtime.initialize()
                self.assertTrue(os.environ['PATH'].startswith(str(root/'bin')))
                self.assertEqual(runtime.host_environment()['PATH'], '/usr/bin')
                self.assertEqual(runtime.host_environment()['ALSA_CONFIG_DIR'], '/custom/alsa')

    def test_frozen_installer_keeps_runtime_for_menu_and_service(self):
        from toughbook import integration
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)/'bundle'
            content = root/'_internal'
            data = content/'data'
            data.mkdir(parents=True)
            source = Path(__file__).resolve().parents[1]
            import shutil
            shutil.copytree(source/'data', data, dirs_exist_ok=True)
            (root/'toughbook-tools').write_text('executable')
            with patch.dict(os.environ, {'XDG_CONFIG_HOME': folder+'/config', 'XDG_DATA_HOME': folder+'/data'}), \
                 patch.object(runtime, 'frozen', return_value=True), \
                 patch.object(runtime, 'application_root', return_value=root), \
                 patch.object(runtime, 'resources', side_effect=lambda target=None: Path(target)/'_internal' if target is not None else content), \
                 patch.object(integration.subprocess, 'run', return_value=Mock(returncode=0)):
                service = Path(folder)/'config/systemd/user/toughbook-buttons.service'
                service.parent.mkdir(parents=True)
                service.write_text('previous')
                target = integration.install_app()
                _, launcher, hidden = integration.paths()
                self.assertTrue((target/'toughbook-tools').exists())
                self.assertIn('"--tool" "app"', launcher.read_text())
                self.assertIn('"--tool" "buttons"', service.read_text())
                self.assertNotIn('/usr/bin/python3', service.read_text())
                self.assertNotIn('/usr/bin/python3', hidden.read_text())

    def test_source_dispatcher_exposes_existing_tool_clis(self):
        root = Path(__file__).resolve().parents[1]
        for tool in ('app', 'screen', 'audio', 'buttons', 'check-display'):
            result = subprocess.run([sys.executable, '-B', str(root/'toughbook-tools.py'), '--tool', tool, '--help'],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('usage:', result.stdout)


if __name__ == '__main__':
    unittest.main()
