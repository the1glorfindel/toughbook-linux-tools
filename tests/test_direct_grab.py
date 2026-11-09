"""Exclusive access is limited to the opened dedicated tablet-button device."""
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from toughbook import direct_buttons as direct
from toughbook.common import ToolError


class DedicatedGrabTests(unittest.TestCase):
    def test_grab_requires_character_device_driver_name_and_acpi_ancestry(self):
        for mode, ancestry, name, allowed in (
                (stat.S_IFCHR, 'MAT001F:00', 'Panasonic CF-19 Tablet Buttons', True),
                (stat.S_IFREG, 'MAT001F:00', 'Panasonic CF-19 Tablet Buttons', False),
                (stat.S_IFCHR, 'ordinary-keyboard', 'Panasonic CF-19 Tablet Buttons', False),
                (stat.S_IFCHR, 'MAT001F:00', 'Ordinary Keyboard', False)):
            with self.subTest(mode=mode, ancestry=ancestry, name=name), \
                 tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                device = root / ancestry / 'input0'
                device.mkdir(parents=True)
                (device/'name').write_text(name)
                node = root/'13:77'
                node.mkdir()
                (node/'device').symlink_to(device, target_is_directory=True)
                with patch.object(direct.os, 'fstat', return_value=SimpleNamespace(
                        st_mode=mode, st_rdev=os.makedev(13, 77))), \
                     patch.object(direct.fcntl, 'ioctl') as ioctl:
                    if allowed:
                        direct.grab_dedicated(42, root)
                        ioctl.assert_called_once_with(42, direct.EVIOCGRAB, 1)
                    else:
                        with self.assertRaises(ToolError):
                            direct.grab_dedicated(42, root)
                        ioctl.assert_not_called()

    def test_failed_grab_closes_descriptor_before_retry(self):
        client = direct.Direct.__new__(direct.Direct)
        client.fd = None
        client.last_error = None
        glib = Mock()
        with patch.dict(sys.modules, {'gi.repository': SimpleNamespace(GLib=glib)}), \
             patch.object(direct.buttons, 'devices', return_value=['/dev/input/test-tablet']), \
             patch.object(direct.os, 'open', return_value=42), \
             patch.object(direct, 'grab_dedicated', side_effect=OSError('busy')), \
             patch.object(direct.os, 'close') as close, \
             patch.object(direct.buttons, 'record_status') as status:
            self.assertTrue(client.connect_device())
            close.assert_called_once_with(42)
            self.assertIsNone(client.fd)
            glib.io_add_watch.assert_not_called()
            self.assertIn('busy', status.call_args.kwargs['error'])

    def test_shutdown_closes_exclusive_descriptor(self):
        client = direct.Direct.__new__(direct.Direct)
        client.resume_actions = Mock()
        client.fd, client.watch, client.retry = 42, 10, 11
        glib = Mock()
        with patch.dict(sys.modules, {'gi.repository': SimpleNamespace(GLib=glib)}), \
             patch.object(direct.os, 'close') as close:
            client.close()
        close.assert_called_once_with(42)
        self.assertIsNone(client.fd)
        self.assertEqual(glib.source_remove.call_count, 2)
