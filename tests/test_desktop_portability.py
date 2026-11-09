"""Desktop-independent input, calibration and action recovery, with no live devices."""
from contextlib import ExitStack
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from toughbook import affine, buttons, button_desktop as desktop, distro, screen, session, setup, xinput
from toughbook.direct_buttons import Direct, PACKET
from toughbook.common import ToolError, load_json, save_json

IDENTITY = {'ID_VENDOR_ID': '056a', 'ID_MODEL_ID': '0093', 'ID_USB_INTERFACE_NUM': '01',
            'ID_SERIAL': 'test', 'ID_PATH': 'test-path'}
DEVICE = {'event': 'event99', 'identity': IDENTITY, 'properties': {}}


class CapabilityTests(unittest.TestCase):
    def test_live_compositor_overrides_desktop_environment_name(self):
        dbus = Mock()
        dbus.SessionBus.return_value.name_has_owner.side_effect = lambda name: name == 'org.kde.KWin'
        with patch.dict(os.environ, {'XDG_SESSION_TYPE': 'wayland', 'XDG_CURRENT_DESKTOP': 'GNOME'}), \
             patch.dict('sys.modules', {'dbus': dbus}):
            self.assertEqual(session.compositor(), 'kde')
            dbus.SessionBus.return_value.name_has_owner.return_value = False
            dbus.SessionBus.return_value.name_has_owner.side_effect = lambda name: name == 'org.gnome.Mutter.DisplayConfig'
            self.assertEqual(session.compositor(), 'gnome')
            dbus.SessionBus.return_value.name_has_owner.side_effect = lambda name: False
            self.assertEqual(session.compositor(), 'libinput')

    def test_explicit_x11_wins_over_stale_wayland_environment(self):
        with patch.dict(os.environ, {'XDG_SESSION_TYPE': 'x11', 'WAYLAND_DISPLAY': 'old'}):
            self.assertEqual(session.kind(), 'x11')

    def test_session_type_detection_with_both_or_neither_display_variables(self):
        cases = [({'XDG_SESSION_TYPE': 'x11', 'WAYLAND_DISPLAY': 'stale'}, 'x11'),
                 ({'XDG_SESSION_TYPE': 'wayland', 'DISPLAY': ':1'}, 'wayland'),
                 ({'DISPLAY': ':1'}, 'x11'),
                 ({'DISPLAY': ':1', 'WAYLAND_DISPLAY': 'wayland-1'}, 'wayland')]
        for environment, expected in cases:
            with patch.dict(os.environ, environment, clear=True):
                self.assertEqual(session.kind(), expected)
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(ToolError):
            session.kind()

    def test_inactive_locked_or_unavailable_session_never_authorized(self):
        for props in ({'LockedHint': True}, {}):
            with patch.object(session, 'login_session', return_value=props):
                self.assertFalse(session.active_unlocked())
        with patch.object(session, 'login_session', side_effect=ToolError('inactive')):
            self.assertFalse(session.active_unlocked())
        with patch.object(session, 'login_session', return_value={'LockedHint': False}):
            self.assertTrue(session.active_unlocked())

    def test_logind_filters_uid_remote_inactive_and_ambiguous_sessions(self):
        dbus, manager = Mock(), Mock()
        dbus.SystemBus.return_value.get_object.side_effect = lambda service, path: path
        uid = os.getuid()
        good = {'User': (uid, '/user'), 'Active': True, 'Remote': False,
                'Type': 'x11', 'Id': '1', 'LockedHint': False}
        properties = {'/session/1': good}
        dbus.Interface.side_effect = lambda obj, iface: manager if obj == '/org/freedesktop/login1' else Mock(GetAll=Mock(return_value=properties[obj]))
        manager.ListSessions.return_value = [('1', uid, 'test', 'seat0', '/session/1')]
        with patch.dict('sys.modules', {'dbus': dbus}), patch.dict(os.environ, {'XDG_SESSION_ID': ''}):
            self.assertEqual(session.login_session(), good)
            for bad in ({**good, 'Remote': True}, {**good, 'Active': False},
                        {**good, 'User': (uid + 1, '/other')}, {**good, 'Type': 'tty'}):
                properties['/session/1'] = bad
                with self.assertRaises(ToolError):
                    session.login_session()
            properties['/session/1'] = good
            properties['/session/2'] = {**good, 'Id': '2'}
            manager.ListSessions.return_value.append(('2', uid, 'test', 'seat1', '/session/2'))
            with self.assertRaises(ToolError):
                session.login_session()

    def test_generic_dependency_selection_for_every_family(self):
        for family in ('debian', 'fedora', 'arch'):
            packages, _ = distro.app_packages(family, 'generic', available=lambda p: True)
            self.assertIn('xdg-desktop-portal-gtk', packages)
            self.assertIn('wlr-randr', packages)
            self.assertNotIn('xdg-desktop-portal-kde', packages)
            self.assertNotIn('xdg-desktop-portal-gnome', packages)
            self.assertNotIn('libkscreen', packages)
            self.assertNotIn('libkscreen-bin', packages)

    def test_setup_accepts_unknown_desktop_without_explicit_override(self):
        from contextlib import redirect_stdout
        with patch.dict(os.environ, {'XDG_CURRENT_DESKTOP': 'XFCE'}), \
             patch.object(distro, 'distro_id', return_value='fedora'), \
             patch.object(distro.shutil, 'which', side_effect=lambda p: '/usr/bin/' + p), \
             redirect_stdout(io.StringIO()) as output:
            self.assertEqual(setup.main(['--dry-run']), 0)
        self.assertEqual(json.loads(output.getvalue())['desktop'], 'generic')

    def test_session_start_imports_environment_before_service_restart(self):
        with patch.dict(os.environ, {'DISPLAY': ':7', 'XDG_SESSION_TYPE': 'x11'}, clear=True), \
             patch.object(buttons.subprocess, 'run') as run:
            buttons.start_session()
            self.assertEqual(run.call_args_list[0].args[0],
                             ['systemctl', '--user', 'import-environment', 'DISPLAY', 'XDG_SESSION_TYPE'])
            self.assertEqual(run.call_args_list[1].args[0][-2:], ['restart', 'toughbook-buttons.service'])


class DirectTests(unittest.TestCase):
    def make_reader(self):
        reader = object.__new__(Direct)
        reader.active, reader.buffer, reader.paused, reader.dropped = set(), b'', False, False
        return reader

    def feed(self, reader, *events):
        reader.feed(b''.join(PACKET.pack(0, 0, *event) for event in events))

    def test_only_dedicated_button_edges_trigger_once_and_partial_packets_work(self):
        reader = self.make_reader()
        packet = PACKET.pack(0, 0, 1, 183, 1)
        with patch.object(buttons, 'record_status'), patch.object(buttons, 'execute') as execute, \
             patch.object(buttons, 'load_settings', return_value=buttons.defaults()), \
             patch.object(session, 'active_unlocked', return_value=True):
            reader.feed(packet[:5])
            execute.assert_not_called()
            reader.feed(packet[5:])
            self.feed(reader, (1, 183, 1), (1, 183, 2), (1, 30, 1), (1, 187, 1))
            self.assertEqual(execute.call_count, 1)
            self.feed(reader, (1, 183, 0), (1, 183, 1))
            self.assertEqual(execute.call_count, 2)

    def test_no_actions_while_paused_inactive_or_locked(self):
        for paused, active in ((True, True), (False, False)):
            reader = self.make_reader()
            reader.paused = paused
            with patch.object(buttons, 'record_status'), patch.object(buttons, 'execute') as execute, \
                 patch.object(session, 'active_unlocked', return_value=active):
                self.feed(reader, (1, 183, 1))
                execute.assert_not_called()

    def test_dropped_events_are_discarded_until_resynchronization(self):
        reader = self.make_reader()
        with patch.object(buttons, 'record_status'), patch.object(buttons, 'execute') as execute, \
             patch.object(buttons, 'load_settings', return_value=buttons.defaults()), \
             patch.object(session, 'active_unlocked', return_value=True):
            self.feed(reader, (0, 3, 0), (1, 183, 1))
            execute.assert_not_called()
            self.feed(reader, (0, 0, 0), (1, 183, 1))
            execute.assert_called_once()

    def test_one_failed_action_does_not_disable_other_buttons(self):
        reader = self.make_reader()
        with patch.object(buttons, 'record_status') as record, \
             patch.object(buttons, 'execute', side_effect=[ToolError('missing app'), None]) as execute, \
             patch.object(buttons, 'load_settings', return_value=buttons.defaults()), \
             patch.object(session, 'active_unlocked', return_value=True):
            self.feed(reader, (1, 183, 1), (1, 184, 1))
            self.assertEqual(execute.call_count, 2)
            self.assertTrue(any(c.kwargs.get('error') == 'missing app' for c in record.call_args_list))

    def test_backend_selection_is_persistent_and_portal_is_opt_in(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'XDG_CONFIG_HOME': folder}):
            self.assertEqual(buttons.helper_backend(), 'direct')
            buttons.save_backend('portal')
            self.assertEqual(buttons.helper_backend(), 'portal')
            with self.assertRaises(ToolError):
                buttons.save_backend('unknown')


class PortableCalibrationTests(unittest.TestCase):
    def test_generic_layout_rejects_ambiguous_scaled_rotated_or_external_output(self):
        output = dict(name='LVDS-1', width=1024, height=768, x=0, y=0, scale=1, normal=True)
        self.assertEqual(screen.generic_layout([output]), ('LVDS-1', 1024, 768))
        for outputs in ([], [output, output], [{**output, 'scale': 2}], [{**output, 'normal': False}],
                        [{**output, 'name': 'HDMI-1'}], [{**output, 'x': 100}], [{**output, 'width': 768, 'height': 1024}]):
            with self.assertRaises(ToolError):
                screen.generic_layout(outputs)

    def test_xinput_matches_finger_node_and_preserves_pen(self):
        props = 'Device Node (9): "/dev/input/event99"\nCoordinate Transformation Matrix (10): 1, 0, 0, 0, 1, 0, 0, 0, 1\n'
        def run(*args):
            if args[1:3] == ('list', '--id-only'):
                return Mock(stdout='11\n12\n')
            if args[1] == 'list-props':
                return Mock(stdout=props if args[2] == '12' else props.replace('event99', 'event7'))
            return Mock()
        with patch.object(session, 'kind', return_value='x11'), patch.object(xinput, 'require'), \
             patch.object(xinput, 'udev_properties', return_value=IDENTITY), \
             patch.object(xinput, 'run', side_effect=run) as command:
            device = xinput.XInput(DEVICE)
            self.assertEqual(device.id, '12')
            self.assertEqual(device.get()['matrix'], affine.IDENTITY)
            device.set(affine.IDENTITY)
            command.assert_any_call('xinput', 'set-prop', '12', 'Coordinate Transformation Matrix', *affine.IDENTITY, 0, 0, 1)
            self.assertFalse(any(c.args[1] == 'set-prop' and c.args[2] == '11' for c in command.call_args_list))

    def test_xinput_refuses_wayland_before_querying_or_mutating_xwayland(self):
        with patch.object(session, 'kind', return_value='wayland'), patch.object(xinput, 'run') as run:
            with self.assertRaisesRegex(ToolError, 'native X11'):
                xinput.XInput(DEVICE)
            run.assert_not_called()

    def test_reused_xinput_id_or_event_node_is_never_written(self):
        for changed_node in (False, True):
            props = ['Device Node (9): "/dev/input/event99"\nCoordinate Transformation Matrix (10): 1,0,0,0,1,0,0,0,1\n']
            identity = dict(IDENTITY)
            def run(*args):
                return Mock(stdout='12' if args[1] == 'list' else props[0])
            with patch.object(session, 'kind', return_value='x11'), patch.object(xinput, 'require'), \
                 patch.object(xinput, 'udev_properties', return_value=identity), \
                 patch.object(xinput, 'run', side_effect=run) as command:
                device = xinput.XInput(DEVICE)
                if changed_node:
                    props[0] = props[0].replace('event99', 'event7')
                else:
                    identity['ID_VENDOR_ID'] = 'other-device'
                with self.assertRaises(ToolError):
                    device.set(affine.IDENTITY)
                self.assertFalse(any(c.args[1] == 'set-prop' for c in command.call_args_list))

    def test_libinput_apply_and_restore_work_without_gnome(self):
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            path = Path(folder) / 'screen.json'
            rule = Path(folder) / 'rule'
            save_json(path, {'kind': 'screen', 'backend': 'libinput', 'identity': IDENTITY,
                             'previous': {'rule': None}, 'matrix': affine.IDENTITY, 'status': 'candidate',
                             'size': [1024, 768], 'session': 'old'})
            stack.enter_context(patch.object(screen, 'RULE', rule))
            stack.enter_context(patch.object(screen, 'backend_name', return_value='libinput'))
            stack.enter_context(patch.object(screen, 'find_saved_device', return_value=DEVICE))
            stack.enter_context(patch.object(screen, 'session_token', return_value='new'))
            stack.enter_context(patch.object(screen, 'layout', return_value=('LVDS-1', 1024, 768)))
            install = stack.enter_context(patch.object(screen, 'install_rule'))
            screen.apply_pending(path, privilege='pkexec')
            self.assertEqual(load_json(path)['status'], 'pending-login')
            self.assertEqual(install.call_args.kwargs['privilege'], 'pkexec')
            screen.restore_backup(path, privilege='pkexec')
            self.assertIsNone(install.call_args.args[0])
            self.assertEqual(load_json(path)['status'], 'restored')

    def test_x11_activation_and_restore_retain_previous_persistence(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'XDG_CONFIG_HOME': folder}), \
             patch.object(session, 'kind', return_value='x11'), \
             patch.object(screen, 'find_saved_device', return_value=DEVICE), \
             patch.object(screen, 'layout') as layout, patch.object(screen, 'XInput') as device:
            screen.save_activation({'identity': IDENTITY, 'matrix': affine.IDENTITY})
            screen.activate_x11()
            layout.assert_called_once_with('x11')
            device.return_value.set.assert_called_once_with(affine.IDENTITY)
            previous = {'identity': IDENTITY, 'matrix': [1, 0, .1, 0, 1, .2]}
            screen.restore_activation({'activation': previous})
            self.assertEqual(load_json(screen.activation_path()), previous)
            screen.restore_activation({'activation': None})
            self.assertFalse(screen.activation_path().exists())

    def test_failed_live_recovery_still_removes_unaccepted_login_transform(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'XDG_CONFIG_HOME': folder}):
            screen.save_activation({'identity': IDENTITY, 'matrix': affine.IDENTITY})
            live = Mock()
            live.restore.side_effect = ToolError('device disconnected')
            with self.assertRaisesRegex(ToolError, 'device disconnected'):
                screen.restore_live('x11', DEVICE, {'matrix': affine.IDENTITY, 'activation': None}, live=live)
            self.assertFalse(screen.activation_path().exists())

    def test_x11_acceptance_failure_rolls_back_live_matrix(self):
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            for name in ('desktop_user', 'require', 'check_model'):
                stack.enter_context(patch.object(screen, name))
            stack.enter_context(patch.object(screen, 'backend_name', return_value='x11'))
            stack.enter_context(patch.object(screen, 'layout', return_value=('LVDS-1', 1024, 768)))
            stack.enter_context(patch.object(screen, 'touch_devices', return_value=[DEVICE]))
            stack.enter_context(patch.object(screen, 'backup_path', return_value=Path(folder)/'screen.json'))
            stack.enter_context(patch.object(screen, 'activation_path', return_value=Path(folder)/'activation.json'))
            live = stack.enter_context(patch.object(screen, 'XInput')).return_value
            live.get.return_value = {'matrix': affine.IDENTITY}
            stack.enter_context(patch.object(screen, 'save_activation', side_effect=OSError('disk full')))
            def window(size, callback):
                callback(affine.IDENTITY, 0, affine.TARGETS, size)
                return Mock(run=Mock(return_value=True))
            stack.enter_context(patch.object(screen, 'CalibrationWindow', side_effect=window))
            with self.assertRaises(OSError):
                screen.main([])
            live.restore.assert_called_once()
            self.assertEqual(load_json(Path(folder)/'screen.json')['status'], 'cancelled')


class PortableActionTests(unittest.TestCase):
    def test_x11_rotation_composes_touch_and_rolls_back_both_on_failure(self):
        for failure in (False, True):
            touch = Mock()
            touch.get.return_value = {'matrix': affine.IDENTITY}
            old = {'name': 'LVDS-1', 'rotation': 'normal'}
            new = {'name': 'LVDS-1', 'rotation': 'right'}
            with patch.object(desktop, '_x11_output', side_effect=[old, old, old] if failure else [old, new]), \
                 patch.object(desktop, '_settle_x11_touch') as settle, \
                 patch.object(desktop, '_save_recovery'), patch.object(desktop, 'run') as run, \
                 patch('toughbook.common.touch_devices', return_value=[DEVICE]), \
                 patch.object(xinput, 'XInput', return_value=touch):
                if failure:
                    with self.assertRaisesRegex(ToolError, 'restored'):
                        desktop._rotate_x11()
                    settle.assert_called_once_with(touch, affine.IDENTITY)
                    self.assertEqual(run.call_args.args[-1], 'normal')
                else:
                    desktop._rotate_x11()
                    settle.assert_called_once_with(touch, desktop.X11_ROTATIONS['right'])

    def test_wlroots_rotation_and_rejected_transform_recovery(self):
        old = {'name': 'LVDS-1', 'enabled': True, 'transform': 'normal'}
        new = {**old, 'transform': '90'}
        with patch.object(desktop, '_wlr_output', side_effect=[old, new]), \
             patch.object(desktop, '_save_recovery'), patch.object(desktop, 'run') as run:
            desktop._rotate_wlr()
            self.assertEqual(run.call_args.args, ('wlr-randr', '--output', 'LVDS-1', '--transform', '90'))
        with patch.object(desktop, '_wlr_output', return_value=old), \
             patch.object(desktop, '_save_recovery'), patch.object(desktop, 'run') as run:
            with self.assertRaisesRegex(ToolError, 'previous orientation restored'):
                desktop._rotate_wlr()
            self.assertEqual(run.call_count, 2)
            self.assertEqual(run.call_args.args[-1], 'normal')

    def test_unknown_compositor_rotation_has_actionable_command_fallback(self):
        with patch.object(desktop, '_wlr_output', side_effect=ToolError('protocol absent')):
            with self.assertRaisesRegex(ToolError, 'Assign its rotation command'):
                desktop._rotate_wlr()

    def test_lock_uses_logind_when_no_shell_screen_saver_interface_exists(self):
        dbus = Mock()
        dbus.SessionBus.return_value.get_object.side_effect = RuntimeError('No screen saver')
        with patch.object(desktop, 'dbus_module', return_value=dbus), \
             patch.object(session, 'login_session', return_value={'Id': 'test-session'}), \
             patch.object(desktop, 'run') as run:
            desktop._lock()
            run.assert_called_once_with('loginctl', 'lock-session', 'test-session')

    def test_portable_launcher_and_keyboard_use_argument_vectors(self):
        with patch.object(desktop.shutil, 'which', side_effect=lambda cmd: cmd == 'fuzzel'), \
             patch.object(buttons, 'execute') as spawn:
            desktop._launcher('libinput')
            spawn.assert_called_once_with({'type': 'command', 'value': 'fuzzel'})
        with patch.object(desktop, '_keyboard_process', None), \
             patch.object(desktop.shutil, 'which', side_effect=lambda cmd: cmd == 'onboard'), \
             patch.object(desktop.subprocess, 'Popen') as spawn:
            spawn.return_value.poll.return_value = None
            desktop._portable_keyboard('x11')
            desktop._portable_keyboard('x11')
            spawn.assert_called_once_with(['onboard'], start_new_session=True)
            spawn.return_value.terminate.assert_called_once()


if __name__ == '__main__':
    unittest.main()
