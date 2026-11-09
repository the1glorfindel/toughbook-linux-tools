"""Mocked coverage for desktop button actions; no host desktop is touched."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from toughbook import button_desktop as desktop
from toughbook.common import ToolError


class BackendTests(unittest.TestCase):
    def test_x11_mapping_is_reapplied_after_desktop_reset(self):
        target = desktop.X11_ROTATIONS['right']
        touch = Mock()
        touch.get.side_effect = [{'matrix': [1, 0, 0, 0, 1, 0]}] + [{'matrix': target}] * 20
        ticks = iter(n / 4 for n in range(100))
        with patch.object(desktop.time, 'monotonic', side_effect=lambda: next(ticks)), \
             patch.object(desktop.time, 'sleep'):
            desktop._settle_x11_touch(touch, target)
        self.assertEqual(touch.set.call_count, 2)
        touch.set.assert_called_with(target)
        self.assertGreater(touch.get.call_count, 1)

    def test_x11_mapping_that_never_stabilizes_fails_boundedly(self):
        touch = Mock()
        touch.get.return_value = {'matrix': [1, 0, 0, 0, 1, 0]}
        ticks = iter(n / 4 for n in range(100))
        with patch.object(desktop.time, 'monotonic', side_effect=lambda: next(ticks)), \
             patch.object(desktop.time, 'sleep'):
            with self.assertRaisesRegex(ToolError, 'keeps resetting'):
                desktop._settle_x11_touch(touch, desktop.X11_ROTATIONS['right'])

    def test_gnome_launcher_uses_public_overview_property(self):
        dbus = Mock()
        with patch.object(desktop, 'dbus_module', return_value=dbus):
            desktop._launcher('gnome')
        dbus.Interface.return_value.Set.assert_called_once_with(
            'org.gnome.Shell', 'OverviewActive', True, timeout=10)

    def test_x11_uses_live_shell_for_actions_but_native_rotation(self):
        for shell, backend in (('org.gnome.Shell', 'gnome'),
                               ('org.kde.plasmashell', 'kde'), ('', 'x11')):
            dbus = Mock()
            dbus.SessionBus.return_value.name_has_owner.side_effect = lambda name: name == shell
            with patch.object(desktop, 'backend_name', return_value='x11'), \
                 patch.object(desktop, 'dbus_module', return_value=dbus), \
                 patch.object(desktop, '_keyboard') as keyboard, \
                 patch.object(desktop, '_launcher') as launcher, \
                 patch.object(desktop, '_rotate_x11') as rotate:
                desktop.perform('keyboard')
                desktop.perform('launcher')
                desktop.perform('rotate')
                keyboard.assert_called_once_with(backend)
                launcher.assert_called_once_with(backend)
                rotate.assert_called_once_with()

    def test_accepts_x11_and_unknown_wayland_desktops(self):
        with patch.dict(os.environ, {'XDG_SESSION_TYPE': 'x11', 'XDG_CURRENT_DESKTOP': 'XFCE'}):
            self.assertEqual(desktop.backend_name(), 'x11')
        with patch.dict(os.environ, {'XDG_SESSION_TYPE': 'wayland', 'XDG_CURRENT_DESKTOP': 'sway'}), \
             patch.dict('sys.modules', {'dbus': None}):
            self.assertEqual(desktop.backend_name(), 'libinput')

    def test_unknown_action_rejected(self):
        with self.assertRaises(ToolError):
            desktop.perform('eval')

    def test_keyboard_toggles_gnome_accessibility_setting(self):
        with patch.object(desktop, 'backend_name', return_value='gnome'), \
             patch.object(desktop, 'require') as require, \
             patch.object(desktop, 'run', side_effect=[Mock(stdout='false'), Mock()]) as run:
            desktop.perform('keyboard')
        require.assert_called_once_with('gsettings')
        self.assertEqual(run.call_args.args[-1], 'true')

    def test_kde_keyboard_force_activates_when_active_but_not_visible(self):
        props, keyboard = Mock(), Mock()
        props.Get.side_effect = [True, False]  # available, visible; active is intentionally irrelevant
        dbus, obj = Mock(), Mock()
        dbus.SessionBus.return_value.get_object.return_value = obj
        dbus.Interface.side_effect = [props, keyboard]
        with patch.object(desktop, 'dbus_module', return_value=dbus):
            desktop._keyboard('kde')
        keyboard.forceActivate.assert_called_once_with(timeout=10)
        props.Set.assert_not_called()

    def test_kde_keyboard_hides_visible_and_rejects_unavailable(self):
        props, dbus = Mock(), Mock()
        props.Get.side_effect = [True, True]
        dbus.Interface.return_value = props
        with patch.object(desktop, 'dbus_module', return_value=dbus):
            desktop._keyboard('kde')
        props.Set.assert_called_once_with('org.kde.kwin.VirtualKeyboard', 'active', False, timeout=10)

        props.Get.side_effect = [False]
        with patch.object(desktop, 'dbus_module', return_value=dbus), \
             patch.object(desktop, '_portable_keyboard', side_effect=ToolError('No provider')), \
             self.assertRaises(ToolError):
            desktop._keyboard('kde')

    def test_kde_launcher(self):
        dbus = Mock()
        with patch.object(desktop, 'backend_name', return_value='kde'), \
             patch.object(desktop, 'dbus_module', return_value=dbus):
            desktop.perform('launcher')
        dbus.SessionBus.return_value.get_object.assert_called_once_with('org.kde.plasmashell', '/PlasmaShell')


class RotationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        patcher = patch.object(desktop, 'state_dir', return_value=Path(temporary.name))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_kde_only_active_internal_and_preserves_on_failure(self):
        output = {'name': 'eDP-1', 'enabled': True, 'rotation': 1}
        with patch.object(desktop, '_internal_kde_output', side_effect=[output, {**output, 'rotation': 8}]), \
             patch.object(desktop, 'run') as run:
            desktop._rotate_kde()
        self.assertEqual(run.call_args.args, ('kscreen-doctor', 'output.eDP-1.rotation.right'))

        with patch.object(desktop, '_internal_kde_output', return_value=output), \
             patch.object(desktop, 'run', side_effect=[ToolError('apply'), None]) as run:
            with self.assertRaises(ToolError):
                desktop._rotate_kde()
        self.assertEqual(run.call_args_list[1].args, ('kscreen-doctor', 'output.eDP-1.rotation.normal'))

    def test_kde_no_change_result_is_recovered(self):
        output = {'name': 'eDP-1', 'enabled': True, 'rotation': 1}
        with patch.object(desktop, '_internal_kde_output', side_effect=[output, output, output]), \
             patch.object(desktop, 'run') as run, self.assertRaises(ToolError):
            desktop._rotate_kde()
        self.assertEqual(run.call_count, 2)

    def test_kde_verification_error_rolls_back(self):
        output = {'name':'eDP-1','enabled':True,'rotation':1}
        with patch.object(desktop,'_internal_kde_output',side_effect=[output, ToolError('readback'), output]), patch.object(desktop,'run') as run:
            with self.assertRaisesRegex(ToolError,'previous rotation was restored'):
                desktop._rotate_kde()
            self.assertEqual(run.call_args.args[-1], 'output.eDP-1.rotation.normal')

    def test_gnome_rotation_preserves_all_logical_monitor_fields(self):
        spec = ('eDP-1', 'vendor', 'panel', 'serial')
        logical = (0, 0, 1.25, 0, True, [spec], {'underscanning': True})
        modes = [('mode-id', 1024, 768, 60., 1., [1.], {'is-current': True})]
        state = (12, [(spec, modes, {'is-underscanning': True})], [logical], {})
        applied_logical = (0, 0, 1.25, 1, True, [spec], {'underscanning': True})
        applied_state = (13, [(spec, modes, {'is-underscanning': True})], [applied_logical], {})
        iface = Mock()
        iface.GetCurrentState.return_value = applied_state
        dbus = Mock()
        dbus.Interface.return_value = iface
        with patch.object(desktop, '_gnome_state', return_value=(dbus, state, object())):
            desktop._rotate_gnome()
        args = iface.ApplyMonitorsConfig.call_args.args
        self.assertEqual(args[0:2], (12, 1))
        changed = args[2][0]
        self.assertEqual(changed, (0, 0, 1.25, 1, True, [('eDP-1', 'mode-id', {'underscanning': True})]))

    def test_gnome_apply_failure_reapplies_original(self):
        spec = ('eDP-1', 'vendor', 'panel', 'serial')
        logical = (0, 0, 1.0, 2, True, [spec], {})
        modes = [('mode-id', 1024, 768, 60., 1., [1.], {'is-current': True})]
        state = (4, [(spec, modes, {})], [logical], {})
        iface = Mock()
        iface.GetCurrentState.return_value = state
        iface.ApplyMonitorsConfig.side_effect = [RuntimeError('rejected'), None]
        dbus = Mock()
        dbus.Interface.return_value = iface
        with patch.object(desktop, '_gnome_state', return_value=(dbus, state, object())):
            with self.assertRaises(ToolError):
                desktop._rotate_gnome()
        self.assertEqual(iface.ApplyMonitorsConfig.call_count, 2)
        self.assertEqual(iface.ApplyMonitorsConfig.call_args_list[1].args[2],
                         [(0, 0, 1.0, 2, True, [('eDP-1', 'mode-id', {})])])

    def test_gnome_missing_current_mode_rejected_without_apply(self):
        spec = ('eDP-1', 'vendor', 'panel', 'serial')
        logical = (0, 0, 1.0, 0, True, [spec], {})
        state = (4, [(spec, [], {})], [logical], {})
        iface, dbus, obj = Mock(), Mock(), object()
        dbus.Interface.return_value = iface
        with patch.object(desktop, '_gnome_state', return_value=(dbus, state, obj)), \
             self.assertRaises(ToolError):
            desktop._rotate_gnome()
        iface.ApplyMonitorsConfig.assert_not_called()

    def test_gnome_external_active_display_rejected(self):
        internal = ('eDP-1', 'vendor', 'panel', 'serial')
        external = ('HDMI-1', 'vendor', 'monitor', 'serial')
        logical = [(0, 0, 1.0, 0, True, [internal], {}),
                   (1024, 0, 1.0, 0, False, [external], {})]
        state = (4, [], logical, {})
        with patch.object(desktop, '_gnome_state', return_value=(Mock(), state, object())), \
             self.assertRaises(ToolError):
            desktop._rotate_gnome()

    def test_atomic_recovery_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(desktop, 'state_dir', return_value=Path(tmp)):
            desktop._save_recovery({'backend': 'gnome', 'state': (1, 2)})
            path = Path(tmp) / 'button-desktop' / 'display-recovery.json'
            self.assertEqual(json.loads(path.read_text())['backend'], 'gnome')
            self.assertEqual(list(path.parent.iterdir()), [path])


if __name__ == '__main__':
    unittest.main()
