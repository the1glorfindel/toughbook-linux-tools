"""Focused offscreen tests for the graphical audio page."""
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from PySide6.QtCore import QEvent, QEventLoop, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from toughbook import audio
from toughbook.audio_gui import AudioPage


APP = QApplication.instance() or QApplication([])
DEVICE = {'name': 'alsa_card.test', 'index': 7, 'codec': '10ec0269:ALC269VC'}


class AudioPageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='audio-gui-tests-')
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {
            'XDG_STATE_HOME': str(Path(self.temp.name) / 'state'),
            'XDG_CONFIG_HOME': str(Path(self.temp.name) / 'config'),
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.page = AudioPage()
        self.prompt_count = 0

    def tearDown(self):
        thread = self.page._thread
        if thread is not None:
            self.page.cancel_operation()
            thread.wait(5000)
        self.page.close()
        self.page.deleteLater()
        APP.sendPostedEvents(None, QEvent.DeferredDelete)
        APP.processEvents()
        APP.sendPostedEvents(None, QEvent.DeferredDelete)

    def wait_until_idle(self):
        loop = QEventLoop()
        self.page.busy_changed.connect(lambda busy: loop.quit() if not busy else None)
        QTimer.singleShot(5000, loop.quit)
        loop.exec()
        self.assertIsNone(self.page._thread)

    def test_status_populates_supported_device_and_backups(self):
        backup = Path(self.temp.name) / 'state/toughbook-fedora-tools/audio-123.json'
        backup.parent.mkdir(parents=True)
        backup.write_text('{}')
        with patch.object(audio, 'cards', return_value=[DEVICE]):
            self.page.refresh_status()
            self.wait_until_idle()
        self.assertEqual(self.page.device_combo.currentData(), DEVICE)
        self.assertEqual(self.page.backup_combo.currentData(), str(backup))
        self.assertIn('1 supported device', self.page.status_label.text())

    def test_repair_runs_in_worker_and_marshals_all_three_prompts(self):
        main_thread = threading.get_ident()

        def repair(device, confirm_fn, start_fn, cancel_event, log_fn):
            self.assertEqual(device, DEVICE)
            self.assertNotEqual(threading.get_ident(), main_thread)
            self.assertTrue(start_fn('Unplug headphones and continue?'))
            self.assertTrue(confirm_fn('Did you hear the INTERNAL speaker?'))
            self.assertTrue(confirm_fn('Does the internal speaker STILL work?'))
            log_fn('synthetic repair completed')
            return 0

        with patch.object(audio, 'repair', side_effect=repair):
            self.page.device_combo.addItem(DEVICE['name'], DEVICE)
            # Run an offscreen timer that accepts each queued dialog.
            QTimer.singleShot(20, self._accept_visible_prompts)
            self.page.repair_selected()
            self.wait_until_idle()

        self.assertEqual(self.prompt_count, 3)
        self.assertIn('synthetic repair completed', self.page.output.toPlainText())

    def _accept_visible_prompts(self):
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QMessageBox) and widget.isVisible():
                self.prompt_count += 1
                widget.button(QMessageBox.Yes).click()
                QTimer.singleShot(20, self._accept_visible_prompts)
                return


if __name__ == '__main__':
    unittest.main()
