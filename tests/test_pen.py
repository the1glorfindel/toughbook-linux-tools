"""Pen side-button mappings use KDE's native device-scoped setting."""
from unittest.mock import patch,Mock
from test_tools import TemporaryState
from toughbook import pen
from toughbook.common import ToolError,load_json,save_json


class PenTests(TemporaryState):
    def setUp(self):
        super().setUp()
        self.context={'name':'Wacom ISDv4 93 Pen','reader':'kreadconfig5','writer':'kwriteconfig5','plugin':'kwin5_plugin_buttonrebinds','api':Mock()}
        self.value=None
        self.connection=patch.object(pen,'connect',return_value=self.context);self.connection.start();self.addCleanup(self.connection.stop)
        self.reader=patch.object(pen,'read',side_effect=lambda c:self.value);self.reader.start();self.addCleanup(self.reader.stop)
        self.writer=patch.object(pen,'write',side_effect=self.write);self.writer.start();self.addCleanup(self.writer.stop)

    def write(self,context,value):self.value=value

    def test_actions_and_default(self):
        for action,value in pen.ACTIONS.items():
            self.assertEqual(pen.apply(action)['action'],action)
            self.assertEqual(self.value,value)

    def test_mapping_targets_pen_side_button_only(self):
        args=pen.arguments(self.context)
        self.assertEqual(args[-2:],['--key','331'])
        self.assertIn('TabletTool',args);self.assertIn('Wacom ISDv4 93 Pen',args)
        self.assertNotIn('Finger',' '.join(args))

    def test_original_mapping_survives_repeated_changes(self):
        self.value='Key,Ctrl+Z'
        pen.apply('right');pen.apply('left')
        self.assertEqual(load_json(pen.backup_path())['previous'],'Key,Ctrl+Z')
        pen.restore();self.assertEqual(self.value,'Key,Ctrl+Z')
        self.assertFalse(pen.backup_path().exists())

    def test_no_previous_override_is_restored_by_deletion(self):
        pen.apply('right');pen.restore();self.assertIsNone(self.value)

    def test_restore_readback_failure_keeps_backup(self):
        self.value='Key,Ctrl+Z'
        pen.apply('right')
        original = self.write
        def ignored_restore(context, value):
            if value != 'Key,Ctrl+Z':
                original(context, value)
        with patch.object(pen, 'write', side_effect=ignored_restore):
            with self.assertRaisesRegex(ToolError, 'did not retain'):
                pen.restore()
        self.assertTrue(pen.backup_path().exists())

    def test_unknown_action_is_rejected_without_writes(self):
        with self.assertRaises(ToolError):pen.apply('shell-command')
        self.assertIsNone(self.value)

    def test_foreign_device_backup_is_rejected(self):
        save_json(pen.backup_path(),{'kind':'pen-side-button','device':'Other Pen','previous':None})
        with self.assertRaisesRegex(ToolError,'another device'):pen.apply('right')
        self.assertIsNone(self.value)

    def test_custom_mapping_is_reported_without_replacement(self):
        self.value='Key,Alt+F4'
        self.assertEqual(pen.status()['action'],'custom');self.assertEqual(self.value,'Key,Alt+F4')


    def test_restore_never_unloads_originally_disabled_plugin(self):
        self.context['loaded']=False
        pen.apply('right');pen.restore()
        self.context['api'].UnloadPlugin.assert_not_called()
        self.context['api'].LoadPlugin.assert_not_called()


class PenAvailabilityTests(__import__('unittest').TestCase):
    def test_gnome_and_x11_are_explicitly_unavailable(self):
        for backend,kind in [('gnome','wayland'),('x11','x11')]:
            with patch.object(pen.session,'compositor',return_value=backend),patch.object(pen.session,'kind',return_value=kind):
                with self.assertRaisesRegex(ToolError,'KDE Plasma Wayland'):pen.connect()
