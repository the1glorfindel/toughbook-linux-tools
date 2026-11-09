"""Identification observes the helper while the dedicated device stays grabbed."""
import io
import sys
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import Mock, patch

from toughbook import buttons
from toughbook.direct_buttons import Direct, PACKET
from toughbook.common import ToolError


class HelperMonitorTests(unittest.TestCase):
    def test_pause_status_clears_on_resume_without_erasing_other_errors(self):
        portal = buttons.Portal.__new__(buttons.Portal)
        portal.paused = False
        glib = Mock()
        with patch.dict(sys.modules, {'gi.repository': SimpleNamespace(GLib=glib)}), \
             patch.object(buttons, 'record_status') as status:
            portal.pause_actions()
            status.assert_called_with(paused=True, error='')
            portal.resume_actions()
            status.assert_called_with(paused=False)
            self.assertFalse(portal.paused)

    def test_paused_direct_reader_forwards_paired_edges_without_actions(self):
        reader = Direct.__new__(Direct)
        reader.buffer = b''
        reader.active = set()
        reader.dropped = False
        reader.paused = True
        reader.notify_button = Mock()
        events = [(1, 183, 1), (1, 183, 2), (1, 183, 1), (1, 183, 0), (1, 30, 1)]
        with patch.object(buttons, 'record_status'), patch.object(buttons, 'execute') as execute:
            reader.feed(b''.join(PACKET.pack(0, 0, *event) for event in events))
        self.assertEqual([call.args for call in reader.notify_button.call_args_list],
                         [('Keyboard', 'pressed'), ('Keyboard', 'released')])
        execute.assert_not_called()

    def test_monitor_follows_helper_signals_and_cleans_up_on_disconnect(self):
        dbus, glib = Mock(), Mock()
        bus = dbus.SessionBus.return_value
        bus.name_has_owner.return_value = True
        def run():
            callback = bus.add_signal_receiver.call_args_list[0].args[0]
            callback('Keyboard', 'pressed')
            callback('Keyboard', 'released')
            callback('ordinary key', 'pressed')
            stopped = bus.add_signal_receiver.call_args_list[1].args[0]
            stopped(buttons.CONTROL_IFACE, ':1.1', '')
        glib.MainLoop.return_value.run.side_effect = run
        output = io.StringIO()
        with patch.dict(sys.modules, {'dbus': dbus, 'dbus.mainloop.glib': Mock(),
                                      'gi.repository': SimpleNamespace(GLib=glib)}), redirect_stdout(output):
            with self.assertRaisesRegex(ToolError, 'helper stopped'):
                buttons.monitor_helper()
        self.assertIn('Keyboard pressed', output.getvalue())
        self.assertIn('Keyboard released', output.getvalue())
        self.assertNotIn('ordinary key', output.getvalue())
        glib.MainLoop.return_value.quit.assert_called_once()
        bus.close.assert_called_once()
        self.assertEqual(bus.add_signal_receiver.return_value.remove.call_count, 2)
        self.assertEqual(bus.add_signal_receiver.call_args_list[0].kwargs['bus_name'], buttons.CONTROL_IFACE)

    def test_no_running_helper_allows_standalone_monitor(self):
        dbus = Mock()
        dbus.SessionBus.return_value.name_has_owner.return_value = False
        with patch.dict(sys.modules, {'dbus': dbus, 'dbus.mainloop.glib': Mock(),
                                      'gi.repository': SimpleNamespace(GLib=Mock())}):
            self.assertFalse(buttons.monitor_helper())
        dbus.SessionBus.return_value.close.assert_called_once()
        dbus.SessionBus.return_value.add_signal_receiver.assert_not_called()
