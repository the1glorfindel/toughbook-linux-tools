"""Button settings, portal and lifecycle regression tests. SPDX-License-Identifier: MIT"""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from toughbook import buttons as b
from toughbook.common import ToolError


class ButtonsTests(unittest.TestCase):
    def test_defaults_and_config_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'XDG_CONFIG_HOME':folder}):
            self.assertEqual(b.load_settings(), b.defaults())
            data = b.defaults()
            data['key'] = {'type':'command', 'value':'/bin/echo "two words"'}
            b.save_json(b.settings_path(), b.validate(data))
            self.assertEqual(b.load_settings(), data)
            self.assertEqual(b.settings_path().stat().st_mode & 0o777, 0o600)

    def test_bad_assignments_do_not_save(self):
        for assignment in ({'type':'builtin','value':'bad'}, {'type':'command','value':''},
                           {'type':'application','value':'/tmp/bad.desktop'}, {'type':'unknown','value':'x'}):
            data = b.defaults()
            data['key'] = assignment
            with self.assertRaises(ToolError): b.validate(data)

    def test_commands_are_argument_vectors_shell_is_explicit(self):
        import sys
        gi = Mock()
        process = Mock()
        with patch.dict(sys.modules, {'gi':gi,'gi.repository':gi.repository}), patch.object(b.shutil,'which',return_value='/bin/echo'), patch.object(b.subprocess,'Popen',return_value=process) as launch:
            b.execute({'type':'command','value':'echo "two words" "$(touch nope)"'})
            self.assertEqual(launch.call_args.args[0], ['systemd-run','--user','--scope','--quiet','--collect','--','echo','two words','$(touch nope)'])
            b.execute({'type':'shell','value':'echo hi | cat'})
            self.assertEqual(launch.call_args.args[0][-3:], ['/bin/sh','-c','echo hi | cat'])

    def test_application_uses_independent_scope_and_desktop_file(self):
        import sys
        gi=Mock()
        app=gi.repository.Gio.DesktopAppInfo.new.return_value
        app.get_filename.return_value='/usr/share/applications/test with spaces.desktop'
        with patch.dict(sys.modules, {'gi':gi,'gi.repository':gi.repository}), patch.object(b.shutil,'which',return_value='/usr/bin/gio'), patch.object(b.subprocess,'Popen') as launch:
            b.execute({'type':'application','value':'test.desktop'})
            self.assertEqual(launch.call_args.args[0][-3:], ['--tool', 'launch-application', 'test.desktop'])
            self.assertIn('--scope',launch.call_args.args[0])

    def test_missing_command_actionable(self):
        with patch.object(b.shutil,'which',return_value=None):
            with self.assertRaisesRegex(ToolError,'missing'):
                b.execute({'type':'command','value':'nonexistent'})

    def test_repeats_and_foreign_sessions_ignored(self):
        portal = object.__new__(b.Portal)
        portal.session='/session/ours'
        portal.active=set()
        with patch.object(b,'record_status'), patch.object(b,'load_settings',return_value=b.defaults()), patch.object(b,'execute') as execute:
            portal.activated('/other','key',0,{})
            portal.activated('/session/ours','key',1,{})
            portal.activated('/session/ours','key',2,{})
            self.assertEqual(execute.call_count,1)
            portal.deactivated('/session/ours','key',3,{})
            portal.activated('/session/ours','key',4,{})
            self.assertEqual(execute.call_count,2)

    def test_identification_pause_records_button_without_launching(self):
        portal = object.__new__(b.Portal)
        portal.session = '/session/ours'
        portal.active = set()
        portal.paused = True
        with patch.object(b, 'record_status') as status, patch.object(b, 'execute') as execute, \
             patch.object(b, 'load_settings', return_value=b.defaults()):
            portal.activated('/session/ours', 'circle', 1, {})
            self.assertEqual(status.call_args.kwargs['last_button'], 'Circle')
            execute.assert_not_called()
            portal.deactivated('/session/ours', 'circle', 2, {})
            portal.paused = False
            portal.activated('/session/ours', 'circle', 3, {})
            execute.assert_called_once()

    def test_conflicts_report_actual_shortcuts(self):
        portal = object.__new__(b.Portal)
        portal.session='/ours'
        with patch.object(b,'record_status') as status:
            portal.changed('/ours',[('keyboard', {'trigger_description':'F13'})])
            self.assertEqual(status.call_args.kwargs['shortcuts'], {'keyboard':'F13'})
            self.assertIn('Unbound',status.call_args.kwargs['error'])

    def test_changed_shortcuts_preserve_other_bindings(self):
        portal = object.__new__(b.Portal)
        portal.session='/ours'
        portal.shortcuts={key: row[2] for key,row in b.BUTTONS.items()}
        with patch.object(b,'record_status') as status:
            portal.changed('/ours',[('keyboard', {'trigger_description':'Ctrl+F13'})])
            self.assertEqual(len(status.call_args.kwargs['shortcuts']),4)
            self.assertEqual(status.call_args.kwargs['error'],'')

    def test_shortcut_configuration_targets_kept_portal_session(self):
        portal=object.__new__(b.Portal)
        portal.session='/session/ours'
        portal.api=Mock()
        portal.dbus=Mock()
        portal.dbus.ObjectPath.side_effect=lambda value: value
        portal.dbus.Dictionary.side_effect=lambda value, **kw: value
        portal.configure()
        portal.api.ConfigureShortcuts.assert_called_once_with('/session/ours','',{},timeout=10)
        portal.session=None
        with self.assertRaises(ToolError): portal.configure()

    def test_host_registry_identity_precedes_session(self):
        portal = object.__new__(b.Portal)
        portal.dbus=Mock()
        portal.dbus.Dictionary.side_effect=lambda data, **kw: data
        portal.obj=object()
        registry=portal.dbus.Interface.return_value
        portal.register_host()
        portal.dbus.Interface.assert_called_once_with(portal.obj,'org.freedesktop.host.portal.Registry')
        registry.Register.assert_called_once_with(b.APP_ID,{},timeout=10)

    def test_portal_request_subscribes_before_method_and_handles_denial(self):
        import sys
        portal = object.__new__(b.Portal)
        portal.dbus=Mock()
        portal.dbus.Dictionary.side_effect=lambda data, **kw: data
        portal.bus=Mock()
        portal.bus.get_unique_name.return_value=':1.42'
        portal.api=Mock()
        portal.pending=[]
        glib=Mock()
        repository=Mock(GLib=glib)
        with patch.dict(sys.modules, {'gi':Mock(),'gi.repository':repository}), patch.object(b,'record_status') as status:
            portal.request('CreateSession',(),Mock())
            self.assertEqual(len(portal.pending),1)
            signal=portal.bus.add_signal_receiver.call_args
            self.assertTrue(signal.kwargs['path'].startswith('/org/freedesktop/portal/desktop/request/1_42/tb'))
            callback=signal.args[0]
            callback(1,{})
            self.assertIn('denied', status.call_args.kwargs['error'])
            portal.bus.add_signal_receiver.return_value.remove.assert_called_once()
            glib.source_remove.assert_called_once()

    def test_monitor_reports_scan_and_paired_edges_ignoring_repeat(self):
        import struct
        import io
        from contextlib import redirect_stdout
        packet = struct.Struct('llHHi')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'tablet-events'
            path.write_bytes(b''.join(packet.pack(0,0,*event) for event in
                [(4,4,8),(1,183,1),(1,183,2),(4,4,8),(1,183,0)]))
            output=io.StringIO()
            with patch.object(b,'devices',return_value=[str(path)]), redirect_stdout(output):
                with self.assertRaisesRegex(ToolError,'disconnected'): b.monitor()
            self.assertEqual(output.getvalue().count('Keyboard pressed'),1)
            self.assertEqual(output.getvalue().count('Keyboard released'),1)
            self.assertIn('Scan code 0x08',output.getvalue())

    def test_portal_restart_cancels_pending_timeout_and_signals(self):
        import sys
        portal=object.__new__(b.Portal)
        match=Mock()
        portal.pending=[{'match':match,'timer':42}]
        portal.session_matches=[Mock()]
        portal.active={'key'}
        portal.session='/old'
        portal.shortcuts={'key':'F16'}
        glib=Mock()
        repository=Mock(GLib=glib)
        with patch.dict(sys.modules, {'gi':Mock(),'gi.repository':repository}), patch.object(b,'record_status'):
            portal.owner_changed('org.freedesktop.portal.Desktop',':1.1','')
            match.remove.assert_called_once()
            glib.source_remove.assert_called_once_with(42)
            self.assertEqual(portal.pending,[])
            self.assertEqual(portal.session_matches,[])
            self.assertIsNone(portal.session)
            self.assertEqual(portal.active,set())

    def test_portal_new_owner_rebuilds_proxy_before_registering(self):
        portal=object.__new__(b.Portal)
        portal.portal_owner=':1.old'
        portal.clear_requests=Mock()
        portal.clear_session_signals=Mock()
        portal.active=set()
        portal.bus=Mock()
        portal.dbus=Mock()
        portal.register_host=Mock()
        portal.start=Mock()
        with patch.object(b,'record_status'):
            portal.owner_changed('org.freedesktop.portal.Desktop',':1.old',':1.new')
        portal.bus.get_object.assert_called_once_with('org.freedesktop.portal.Desktop','/org/freedesktop/portal/desktop')
        portal.register_host.assert_called_once()
        portal.start.assert_called_once()
        portal.clear_requests.reset_mock()
        portal.owner_changed('org.freedesktop.portal.Desktop','',':1.new')
        portal.clear_requests.assert_not_called()

    def test_discovery_excludes_ordinary_keyboard(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name, label in [('event0','AT Translated Set 2 keyboard'),('event1','Panasonic CF-19 Tablet Buttons')]:
                dev=root / ('MAT001F:00' if name=='event1' else 'i8042') / name
                dev.mkdir(parents=True)
                (dev/'name').write_text(label)
                event=root/name
                event.mkdir()
                (event/'device').symlink_to(dev)
            self.assertEqual(b.devices(root), ['/dev/input/event1'])

    def test_uninstall_retains_settings_and_other_files(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'XDG_CONFIG_HOME':folder+'/config','XDG_DATA_HOME':folder+'/data'}), patch.object(b.subprocess,'run'):
            target,menu,autostart=b.integration_paths()
            target.mkdir(parents=True)
            (target/'app.py').write_text('owned')
            menu.parent.mkdir(parents=True)
            menu.write_text('owned')
            other=menu.parent/'other.desktop'
            other.write_text('keep')
            b.save_json(b.settings_path(), b.defaults())
            b.integration(False)
            self.assertFalse(target.exists())
            self.assertFalse(menu.exists())
            self.assertTrue(other.exists())
            self.assertTrue(b.settings_path().exists())

    def test_uninstall_keeps_files_when_service_cannot_be_stopped(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'XDG_CONFIG_HOME':folder+'/config','XDG_DATA_HOME':folder+'/data'}), patch.object(b.subprocess,'run',return_value=Mock(returncode=1,stderr='session bus unavailable')):
            service=Path(folder)/'config/systemd/user/toughbook-buttons.service'
            service.parent.mkdir(parents=True)
            service.write_text('owned')
            with self.assertRaisesRegex(ToolError,'retained'): b.integration(False)
            self.assertTrue(service.exists())

    def test_daemon_setup_failure_records_stopped_and_actionable_error(self):
        import sys
        from toughbook import session
        gi=Mock()
        with tempfile.TemporaryDirectory() as folder, patch.dict(sys.modules, {'gi':gi,'gi.repository':gi.repository}), patch.object(session,'kind',return_value='wayland'), patch.object(b,'state_dir',return_value=Path(folder)), patch.object(b,'record_status') as status, patch.object(b,'Portal',side_effect=ToolError('backend missing')):
            with self.assertRaisesRegex(ToolError,'backend missing'): b.daemon('portal')
            self.assertIsNone(status.call_args.kwargs['pid'])
            self.assertIn('backend missing',status.call_args.kwargs['error'])

    def test_install_generated_desktop_and_service(self):
        import subprocess
        with tempfile.TemporaryDirectory(prefix='cf19 app ') as folder, patch.dict(os.environ, {'XDG_CONFIG_HOME':folder+'/config','XDG_DATA_HOME':folder+'/data'}), patch.object(b.subprocess, 'run') as run:
            b.integration(True)
            target, menu, autostart = b.integration_paths()
            from toughbook.integration import paths as app_paths
            app_target, app_menu, _ = app_paths()
            self.assertTrue((app_target/'toughbook-buttons.py').exists())
            self.assertIn('NoDisplay=true', menu.read_text())
            self.assertTrue(app_menu.exists())
            self.assertIn('--daemon', (Path(folder)/'config/systemd/user/toughbook-buttons.service').read_text())
            self.assertIn('--start-session', autostart.read_text())
            run.assert_any_call(['systemctl','--user','restart','toughbook-buttons.service'],check=True)
            # Reinstalling from an installed copy must not copy a file onto itself.
            b.integration(True)
            self.assertTrue(app_menu.exists())

    def test_launcher_escaping(self):
        self.assertEqual(b.exec_quote('/tmp/a $b% c', systemd=True), '\"/tmp/a $$b%% c\"')
        self.assertIn('\\\\$', b.exec_quote('/tmp/$b'))
        with self.assertRaises(ToolError): b.exec_quote('/tmp/bad\npath')

    def test_unavailable_portal_is_actionable(self):
        with patch.dict('sys.modules', {'dbus':None}):
            self.assertIn('backend', b.portal_status())

if __name__ == '__main__': unittest.main()
