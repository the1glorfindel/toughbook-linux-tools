"""System-wide sensor calibration, migration and rollback behavior without host writes."""
import base64
import json
from pathlib import Path
from contextlib import ExitStack
from unittest.mock import Mock, patch
from types import SimpleNamespace
from test_tools import TemporaryState, DEVICE, IDENTITY
from toughbook import system_touch as system, screen, affine, session, distro
from toughbook.common import ToolError, save_json, load_json


class SystemTouchTests(TemporaryState):
    def setUp(self):
        super().setUp()
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(screen, 'RULE', self.root/'touch.rules'))
        self.stack.enter_context(patch.object(system, 'XORG', self.root/'finger.conf'))
        self.stack.enter_context(patch.object(screen, 'backend_name', return_value='x11'))
        self.stack.enter_context(patch.object(screen, 'layout', return_value=('LVDS-1',1024,768)))
        self.stack.enter_context(patch.object(screen, 'find_saved_device', return_value=DEVICE))
        self.run = self.stack.enter_context(patch.object(system, 'run', return_value=SimpleNamespace(returncode=0)))
        # Model the host driver prerequisite independently of the test machine.
        self.is_file = Path.is_file
        self.stack.enter_context(patch.object(Path, 'is_file', lambda p: True if str(p) in ('/usr/lib/xorg/modules/input/libinput_drv.so', '/usr/lib64/xorg/modules/input/libinput_drv.so') else self.is_file(p)))
        self.path = self.root/'backup.json'
        self.matrix = [1.08, .01, -.03, .002, 1.09, -.02]

    def make(self):
        save_json(self.path, system.candidate(DEVICE, self.matrix, (1024,768)))

    def fake_change(self, expected, desired, privilege):
        self.assertEqual(system.read_files(system.system_paths()),expected)
        for name,content in desired.items():
            p=Path(name)
            if content is None:p.unlink(missing_ok=True)
            else:p.write_bytes(base64.b64decode(content))

    def test_install_and_restore_exact_previous_files_and_user_startup(self):
        screen.RULE.write_text('# previous\n');system.XORG.write_text('# previous xorg\n')
        for p in system.user_paths():p.parent.mkdir(parents=True,exist_ok=True)
        system.user_paths()[1].write_text('old startup')
        self.make(); previous=load_json(self.path)['previous']
        with patch.object(system,'change_files',side_effect=self.fake_change):
            system.apply(self.path,'pkexec')
            self.assertEqual(load_json(self.path)['status'],'pending-reboot')
            self.assertIn('ENV{ID_INPUT_TABLET}=""',screen.RULE.read_text())
            self.assertIn('ID_USB_INTERFACE_NUM}=="01"',screen.RULE.read_text())
            self.assertIn('Driver "libinput"',system.XORG.read_text())
            self.assertTrue(all(not p.exists() for p in system.user_paths()))
            system.restore(self.path,'pkexec')
        self.assertEqual(system.read_files(system.system_paths()),previous['system_files'])
        self.assertEqual(system.read_files(system.user_paths()),previous['user_files'])

    def test_install_refuses_stale_system_file(self):
        self.make();system.XORG.write_text('administrator change')
        with patch.object(system,'change_files') as write:
            with self.assertRaisesRegex(ToolError,'changed'):system.apply(self.path,'sudo')
            write.assert_not_called()

    def test_unrelated_xinput_startup_is_not_deleted(self):
        p=system.user_paths()[0];p.parent.mkdir(parents=True);p.write_text('other input device')
        self.make()
        with patch.object(system,'change_files') as write:
            with self.assertRaisesRegex(ToolError,'unrelated'):system.apply(self.path,'sudo')
            write.assert_not_called()
        self.assertEqual(p.read_text(),'other input device')

    def test_permission_denial_leaves_user_files_and_system_files_unchanged(self):
        self.make();previous=load_json(self.path)['previous']
        with patch.object(system,'change_files',side_effect=ToolError('cancelled')):
            with self.assertRaisesRegex(ToolError,'cancelled'):system.apply(self.path,'pkexec')
        self.assertEqual(system.read_files(system.system_paths()),previous['system_files'])
        self.assertEqual(system.read_files(system.user_paths()),previous['user_files'])

    def test_failure_after_system_install_rolls_back(self):
        self.make();previous=load_json(self.path)['previous']
        self.run.side_effect=[ToolError('reload failed'),SimpleNamespace(returncode=0)]
        with patch.object(system,'change_files',side_effect=self.fake_change):
            with self.assertRaisesRegex(ToolError,'reload failed'):system.apply(self.path,'sudo')
        self.assertEqual(system.read_files(system.system_paths()),previous['system_files'])

    def test_restore_refuses_administrator_edit(self):
        self.make()
        with patch.object(system,'change_files',side_effect=self.fake_change):system.apply(self.path,'sudo')
        system.XORG.write_text('new administrator config')
        with self.assertRaisesRegex(ToolError,'changed'):system.restore(self.path,'sudo')

    def test_effective_x11_matrix_composes_driver_once(self):
        from toughbook import xinput
        display=[1,0,.02,0,1,.03]
        with patch.object(xinput,'XInput') as touch,patch.object(system,'driver_matrix',return_value=self.matrix):
            touch.return_value.get.return_value={'matrix':display}
            self.assertEqual(system.baseline('x11',DEVICE),affine.compose(display,self.matrix))

    def test_legacy_activation_skips_driver_calibration(self):
        screen.save_activation({'identity':IDENTITY,'matrix':self.matrix})
        with patch.object(session,'kind',return_value='x11'),patch.object(system,'driver_matrix',return_value=self.matrix),patch.object(screen,'XInput') as touch:
            screen.activate_x11();touch.assert_not_called()

    def test_legacy_measurement_refuses_driver_calibration(self):
        with patch.object(system,'driver_matrix',return_value=self.matrix):
            with self.assertRaisesRegex(ToolError,'double correction'):screen.calibration_state('x11',DEVICE)

    def test_verification_requires_reboot(self):
        self.make()
        with patch.object(system,'change_files',side_effect=self.fake_change):system.apply(self.path,'sudo')
        with self.assertRaisesRegex(ToolError,'Reboot'):system.verify(self.path,DEVICE,'x11',(1024,768))

    def test_ubuntu_and_fedora_dependencies_include_xorg_libinput(self):
        for family,name in [('ubuntu','xserver-xorg-input-libinput'),('fedora','xorg-x11-drv-libinput')]:
            packages,_=distro.app_packages(family,'gnome',available=lambda _:True)
            self.assertIn(name,packages)

    def test_candidate_rejects_wrong_interface(self):
        bad={**DEVICE,'identity':{**IDENTITY,'ID_USB_INTERFACE_NUM':'00'}}
        with self.assertRaisesRegex(ToolError,'Unsupported'):system.candidate(bad,self.matrix,(1024,768))

    def test_kde_installs_effective_matrix_and_restores_old_override(self):
        old={'matrix':','.join(map(str,affine.to_kwin(affine.IDENTITY))),'output':'eDP-1'}
        with patch.object(screen,'backend_name',return_value='kde'),patch.object(screen,'KWin') as kwin,patch.object(system,'change_files',side_effect=self.fake_change):
            kwin.return_value.get.return_value=old
            self.make();system.apply(self.path,'sudo')
            kwin.return_value.set.assert_called_once_with(affine.to_kwin(self.matrix),'eDP-1')
            system.restore(self.path,'sudo')
            kwin.return_value.restore.assert_called_once_with(old)

    def test_kde_refuses_override_changed_after_measurement(self):
        with patch.object(screen,'backend_name',return_value='kde'),patch.object(screen,'KWin') as kwin,patch.object(system,'change_files') as write:
            kwin.return_value.get.return_value={'matrix':'old','output':'eDP-1'}
            self.make()
            kwin.return_value.get.return_value={'matrix':'new','output':'eDP-1'}
            with self.assertRaisesRegex(ToolError,'KDE calibration changed'):system.apply(self.path,'sudo')
            write.assert_not_called()

    def test_verification_checks_driver_and_identity_mapping_after_reboot(self):
        from toughbook import xinput
        self.make()
        with patch.object(system,'change_files',side_effect=self.fake_change):system.apply(self.path,'sudo')
        d=load_json(self.path);d['boot_id']='previous-boot';save_json(self.path,d)
        device={**DEVICE,'properties':{'LIBINPUT_CALIBRATION_MATRIX':' '.join(map(str,self.matrix))}}
        with patch.object(system,'driver_matrix',return_value=self.matrix),patch.object(xinput,'XInput') as touch,patch('toughbook.screen_gui.verify_targets',return_value=True):
            touch.return_value.get.return_value={'matrix':affine.IDENTITY}
            self.assertEqual(system.verify(self.path,device,'x11',(1024,768)),0)
        self.assertEqual(load_json(self.path)['status'],'accepted')

    def test_verification_rejects_double_calibration(self):
        from toughbook import xinput
        self.make()
        with patch.object(system,'change_files',side_effect=self.fake_change):system.apply(self.path,'sudo')
        d=load_json(self.path);d['boot_id']='previous-boot';save_json(self.path,d)
        device={**DEVICE,'properties':{'LIBINPUT_CALIBRATION_MATRIX':' '.join(map(str,self.matrix))}}
        with patch.object(system,'driver_matrix',return_value=self.matrix),patch.object(xinput,'XInput') as touch:
            touch.return_value.get.return_value={'matrix':self.matrix}
            with self.assertRaisesRegex(ToolError,'double calibration'):system.verify(self.path,device,'x11',(1024,768))

    def test_elevated_helper_refuses_arbitrary_targets(self):
        import sys
        p=self.root/'request.json';p.write_text(json.dumps({'expected':{'/tmp/arbitrary':None},'desired':{'/tmp/arbitrary':None}}))
        with patch.object(sys,'argv',['helper',str(p)]):
            with self.assertRaisesRegex(SystemExit,'Invalid target'):exec(compile(system.HELPER,'<test>','exec'),{})

    def test_helper_is_unavailable_without_administrator_authorization(self):
        with patch.object(system.os,'geteuid',return_value=1000):
            with self.assertRaisesRegex(ToolError,'administrator'):system.privileged_helper(self.path)

    def test_privileged_transaction_writes_both_files_and_restores_on_second_failure(self):
        import os,sys,subprocess
        paths=system.system_paths()
        paths[0].write_text('old rule');paths[1].write_text('old xorg')
        expected=system.read_files(paths)
        desired={str(p):base64.b64encode(('new '+p.name).encode()).decode() for p in paths}
        # Redirect only fixed /etc targets to this test's temporary directory.
        helper=system.HELPER.replace('/etc/udev/rules.d/99-toughbook-fedora-touchscreen.rules',str(paths[0])).replace('/etc/X11/xorg.conf.d/99-toughbook-finger-calibration.conf',str(paths[1]))
        request=self.root/'request.json';request.write_text(json.dumps({'expected':expected,'desired':desired}))
        original=os.replace;calls=[]
        def fail_second(src,dst):
            calls.append(dst)
            if len(calls)==2:raise OSError('second install failed')
            return original(src,dst)
        with patch.object(sys,'argv',['helper',str(request)]),patch.object(subprocess,'run'),patch.object(os,'replace',side_effect=fail_second):
            with self.assertRaisesRegex(OSError,'second install failed'):exec(compile(helper,'<test>','exec'),{})
        self.assertEqual(system.read_files(paths),expected)
        with patch.object(sys,'argv',['helper',str(request)]),patch.object(subprocess,'run'):
            exec(compile(helper,'<test>','exec'),{})
        self.assertEqual(system.read_files(paths),desired)

    def test_legacy_restore_refuses_driver_calibration(self):
        save_json(self.path,{'kind':'screen','backend':'x11','identity':IDENTITY,'previous':{'matrix':affine.IDENTITY}})
        with patch.object(system,'driver_matrix',return_value=self.matrix),patch.object(screen,'restore_live') as restore:
            with self.assertRaisesRegex(ToolError,'legacy X11'):screen.restore_backup(self.path)
            restore.assert_not_called()


    def test_missing_host_xorg_driver_fails_before_privilege(self):
        self.make()
        with patch.object(Path,'is_file',return_value=False),patch.object(system,'change_files') as write:
            with self.assertRaisesRegex(ToolError,'host Xorg libinput'):system.apply(self.path,'sudo')
            write.assert_not_called()

    def test_known_guard_is_disabled_and_enablement_restored_without_starting(self):
        guard=self.config/'systemd/user/toughbook-touch-guard.service';guard.parent.mkdir(parents=True)
        guard.write_text('ExecStart=/test/touch-calibration-guard.py')
        self.make()
        with patch.object(system,'change_files',side_effect=self.fake_change):
            system.apply(self.path,'sudo');system.restore(self.path,'sudo')
        calls=[tuple(map(str,c.args)) for c in self.run.call_args_list]
        self.assertIn(('systemctl','--user','disable','--now','toughbook-touch-guard.service'),calls)
        self.assertIn(('systemctl','--user','enable','toughbook-touch-guard.service'),calls)
        self.assertNotIn(('systemctl','--user','start','toughbook-touch-guard.service'),calls)

    def test_unknown_guard_service_is_not_modified(self):
        guard=self.config/'systemd/user/toughbook-touch-guard.service';guard.parent.mkdir(parents=True)
        guard.write_text('ExecStart=/unrelated/service')
        self.make()
        with patch.object(system,'change_files') as write:
            with self.assertRaisesRegex(ToolError,'Unknown touch guard'):system.apply(self.path,'sudo')
            write.assert_not_called()

    def test_default_and_explicit_system_measurement_dispatch(self):
        for args in ([],['--system-wide']):
            with patch.object(screen,'desktop_user'),patch.object(screen,'require'),patch.object(screen,'check_model'),patch.object(screen,'touch_devices',return_value=[DEVICE]),patch.object(system,'measure',return_value=self.path) as measure:
                self.assertEqual(screen.main(args),0)
                measure.assert_called_once_with(DEVICE,'x11',(1024,768))

    def test_verify_does_not_measure(self):
        save_json(self.path,{'kind':'screen','backend':'system','identity':IDENTITY})
        with patch.object(screen,'desktop_user'),patch.object(screen,'require'),patch.object(screen,'check_model'),patch.object(system,'verify',return_value=0) as verify,patch.object(system,'measure') as measure:
            self.assertEqual(screen.main(['--verify',str(self.path)]),0)
            verify.assert_called_once();measure.assert_not_called()

    def test_measurement_modes_are_mutually_exclusive(self):
        with self.assertRaises(SystemExit):screen.main(['--system-wide','--session-only'])

    def test_gui_advanced_and_backup_filtering(self):
        from PySide6.QtWidgets import QApplication
        from toughbook.screen_gui import ScreenPage
        app=QApplication.instance() or QApplication([])
        self.make()
        with patch('toughbook.screen_gui.state_dir',return_value=self.root),patch.object(ScreenPage,'refresh'):
            page=ScreenPage()
        self.assertTrue(page.advanced_options.isHidden())
        self.assertFalse(page.legacy_backups.isChecked())
        self.assertEqual(page.session_button.text(),'Desktop-session calibration (legacy)')
        with patch.object(page,'start_session'),patch.object(page,'_candidate_operation') as op:
            page.start_button.click();op.assert_called_once_with('--system-wide')
        page.close()
