"""Release content/CLI and GNOME lifecycle tests. SPDX-License-Identifier: MIT"""
import base64
from contextlib import ExitStack, redirect_stdout
import importlib.util
import io
import os
import sys
from pathlib import Path
import shlex
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import Mock, patch

from toughbook import affine, common, screen
from test_tools import DEVICE, IDENTITY, TemporaryState

ROOT = Path(__file__).resolve().parents[1]


class GnomeTests(TemporaryState):
    def candidate(self, status='candidate'):
        path = self.root/'candidate with spaces.json'
        common.save_json(path, {'kind':'screen','backend':'gnome','identity':IDENTITY,
                               'previous':{'rule':None},'matrix':affine.IDENTITY,
                               'status':status,'size':[1024,768],'session':'old-session'})
        return path

    def backend_patches(self, stack):
        for name, mock in [('backend_name',Mock(return_value='gnome')),
                           ('find_saved_device',Mock(return_value=DEVICE)),
                           ('session_token',Mock(return_value='new-session')),
                           ('layout',Mock(return_value=('eDP-1',1024,768))),
                           ('desktop_user',Mock()),('check_model',Mock()),('require',Mock())]:
            stack.enter_context(patch.object(screen,name,mock))
        stack.enter_context(patch.object(screen,'RULE',self.root/'system-rule'))

    def test_successful_apply_does_not_claim_live_verification(self):
        path = self.candidate()
        with ExitStack() as stack:
            self.backend_patches(stack)
            install = stack.enter_context(patch.object(screen,'install_rule'))
            screen.apply_pending(path)
        data = common.load_json(path)
        self.assertEqual(data['status'],'pending-login')
        self.assertEqual(data['session'],'new-session')
        self.assertIn(b'LIBINPUT_CALIBRATION_MATRIX',install.call_args.args[0])

    def test_rule_changed_after_measurement_refuses_installation(self):
        path = self.candidate()
        (self.root/'system-rule').write_text('new independent rule')
        with ExitStack() as stack:
            self.backend_patches(stack)
            install = stack.enter_context(patch.object(screen,'install_rule'))
            with self.assertRaises(common.ToolError): screen.apply_pending(path)
            install.assert_not_called()

    def test_verification_requires_new_login_and_expected_matrix(self):
        path = self.candidate('pending-login')
        with ExitStack() as stack:
            self.backend_patches(stack)
            token = stack.enter_context(patch.object(screen,'session_token',return_value='old-session'))
            with self.assertRaisesRegex(common.ToolError,'Log out'): screen.main(['--verify',str(path)])
            token.return_value = 'new-session'
            with self.assertRaisesRegex(common.ToolError,'udev'): screen.main(['--verify',str(path)])

    def test_successful_verification_records_acceptance(self):
        path = self.candidate('pending-login')
        device = {**DEVICE,'properties':{'LIBINPUT_CALIBRATION_MATRIX':'1 0 0 0 1 0'}}
        with ExitStack() as stack:
            self.backend_patches(stack)
            stack.enter_context(patch.object(screen,'find_saved_device',return_value=device))
            window = stack.enter_context(patch.object(screen,'CalibrationWindow'))
            window.return_value.run.return_value = True
            self.assertEqual(screen.main(['--verify',str(path)]),0)
        self.assertEqual(common.load_json(path)['status'],'accepted')

    def test_restore_preexisting_rule_exactly(self):
        path = self.candidate('pending-login')
        data = common.load_json(path)
        data['previous']['rule'] = base64.b64encode(b'# original\n').decode()
        common.save_json(path,data)
        with ExitStack() as stack:
            self.backend_patches(stack)
            install = stack.enter_context(patch.object(screen,'install_rule'))
            screen.restore_backup(path)
            self.assertEqual(install.call_args.args[0],b'# original\n')
        self.assertEqual(common.load_json(path)['status'],'restored')

    def test_commands_quote_paths_for_bash_and_fish(self):
        path = self.root/'backup with spaces.json'
        self.assertEqual(shlex.split(screen.command('--restore',path))[-1],str(path))


class ReleaseTests(unittest.TestCase):
    def test_archive_reproducibility_clean_content_and_extracted_cli(self):
        spec=importlib.util.spec_from_file_location('builder',ROOT/'tools/make-release.py')
        builder=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        with tempfile.TemporaryDirectory(prefix='cf19-release-test-') as folder:
            folder=Path(folder)
            first=builder.build(folder/'first')
            second=builder.build(folder/'second')
            self.assertEqual(first.read_bytes(),second.read_bytes())
            with tarfile.open(first) as archive:
                members=archive.getmembers()
                self.assertTrue(any(m.name.endswith('/LICENSE') for m in members))
                names = {m.name.split('/',1)[1] for m in members}
                self.assertTrue({'toughbook-buttons.py', 'toughbook-tools.py', 'toughbook/integration.py', 'data/org.toughbook.Tools.desktop.in', 'data/org.toughbook.Tools.svg', 'driver/COPYING',
                    'driver/panasonic-hbtn.c', 'driver/hbtn-decode.h',
                    'driver/test-hbtn-decode.c', 'driver/Makefile', 'driver/dkms.conf',
                    'driver/70-panasonic-hbtn.rules', 'driver/install.sh',
                    'driver/uninstall.sh', 'data/org.toughbook.Buttons.desktop.in',
                    'data/org.toughbook.Buttons-autostart.desktop',
                    'data/toughbook-buttons.service.in', 'tools/setup-ubuntu.sh', 'tools/setup-linux.py', 'tools/check-display.py', 'toughbook/setup.py',
                    'docs/README.md', 'docs/ubuntu.md', 'docs/linux.md', 'docs/desktops.md',
                    'toughbook/session.py', 'toughbook/direct_buttons.py', 'toughbook/display_info.py', 'toughbook/xinput.py',
                    'docs/development.md', 'docs/driver-installation.md',
                    'docs/tablet-buttons.md', 'docs/screen-calibration.md',
                    'docs/audio-fix.md'} <= names)
                for member in members:
                    self.assertNotIn('__pycache__',member.name)
                    self.assertFalse(member.name.endswith(('.alsa-state','.json','.txt')))
                    self.assertEqual(member.uid,0)
                    self.assertEqual(member.mtime,0)
                    content=archive.extractfile(member).read()
                    self.assertNotIn(str(Path.home()).encode(),content)
                extract=folder/'extracted with spaces'
                archive.extractall(extract,filter='data')
            release=next(extract.iterdir())
            for name in ['calibrate-screen.py','fix-audio.py','toughbook-buttons.py','toughbook-tools.py', 'tools/setup-linux.py', 'tools/check-display.py']:
                result=subprocess.run(['python3',str(release/name),'--help'],cwd=folder,
                                      capture_output=True,text=True,timeout=10)
                self.assertEqual(result.returncode,0,result.stderr)
                expected = '--expect' if name == 'tools/check-display.py' else '--dry-run' if name == 'tools/setup-linux.py' else '--uninstall' if name in ('toughbook-buttons.py', 'toughbook-tools.py') else '--restore'
                self.assertIn(expected,result.stdout)


class IntegrationTests(unittest.TestCase):
    def test_install_copies_full_project_and_migrates_visible_buttons_launcher(self):
        from toughbook import integration
        with tempfile.TemporaryDirectory(prefix='toughbook integration ') as folder, \
             patch.dict(os.environ, {'XDG_CONFIG_HOME': folder + '/config', 'XDG_DATA_HOME': folder + '/data'}), \
             patch('toughbook.integration.subprocess.run') as run:
            target, launcher, old = integration.paths()
            old.parent.mkdir(parents=True)
            old.write_text('legacy launcher')
            integration.install_app()
            self.assertTrue((target/'driver/install.sh').is_file())
            self.assertTrue((target/'docs/tablet-buttons.md').is_file())
            self.assertIn('Name=Toughbook Tools', launcher.read_text())
            self.assertIn(str(Path(sys.executable)), launcher.read_text())
            self.assertIn('NoDisplay=true', old.read_text())
            self.assertIn('Name=Toughbook Buttons', old.read_text())
            run.assert_called_once()

    def test_uninstall_keeps_settings_helper_and_unrelated_menu_entries(self):
        from toughbook import integration
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'XDG_CONFIG_HOME': folder + '/config', 'XDG_DATA_HOME': folder + '/data'}), patch('toughbook.integration.subprocess.run'):
            target, launcher, _ = integration.paths()
            target.mkdir(parents=True)
            launcher.parent.mkdir(parents=True)
            launcher.write_text('ours')
            other = launcher.parent/'other.desktop'
            other.write_text('keep')
            settings = Path(folder)/'config/toughbook-buttons/settings.json'
            settings.parent.mkdir(parents=True)
            settings.write_text('{}')
            integration.uninstall_app()
            self.assertFalse(target.exists())
            self.assertFalse(launcher.exists())
            self.assertTrue(other.exists())
            self.assertTrue(settings.exists())

    def test_app_upgrade_migrates_inactive_helper_without_starting_it(self):
        from toughbook import integration
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'XDG_CONFIG_HOME': folder + '/config', 'XDG_DATA_HOME': folder + '/data'}), patch('toughbook.integration.subprocess.run') as run:
            run.return_value.returncode = 3
            service = Path(folder)/'config/systemd/user/toughbook-buttons.service'
            service.parent.mkdir(parents=True)
            service.write_text('old unit')
            integration.install_app()
            self.assertIn('toughbook-tools/toughbook-buttons.py', service.read_text())
            calls = [call.args[0] for call in run.call_args_list]
            self.assertNotIn(['systemctl', '--user', 'start', 'toughbook-buttons.service'], calls)

    def test_app_upgrade_restarts_failed_helper_after_restoring_portal_identity(self):
        from toughbook import integration
        def result(command, **kwargs):
            return Mock(returncode=0 if command[2:4] == ['is-failed', '--quiet'] else 3)
        with tempfile.TemporaryDirectory() as folder, \
             patch.dict(os.environ, {'XDG_CONFIG_HOME': folder + '/config', 'XDG_DATA_HOME': folder + '/data'}), \
             patch('toughbook.integration.subprocess.run', side_effect=result) as run:
            service = Path(folder)/'config/systemd/user/toughbook-buttons.service'
            service.parent.mkdir(parents=True)
            service.write_text('old unit')
            integration.install_app()
            _, _, hidden = integration.paths()
            self.assertIn('NoDisplay=true', hidden.read_text())
            self.assertIn(['systemctl', '--user', 'start', 'toughbook-buttons.service'],
                          [call.args[0] for call in run.call_args_list])


if __name__=='__main__':
    unittest.main()
