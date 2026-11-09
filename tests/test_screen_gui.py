"""Qt calibration target behavior. SPDX-License-Identifier: MIT"""
import unittest
from unittest.mock import patch
from pathlib import Path
import tempfile

from PySide6.QtCore import QEvent, QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from toughbook.affine import TARGETS
from toughbook.screen_gui import _Targets
from toughbook.screen_gui import ScreenPage
from toughbook.common import load_json, save_json


APP = QApplication.instance() or QApplication([])


class TargetTests(unittest.TestCase):
    def tearDown(self):
        APP.sendPostedEvents(None, QEvent.DeferredDelete)
        APP.processEvents()
        APP.sendPostedEvents(None, QEvent.DeferredDelete)

    def test_exactly_nine_touch_samples_emit_once(self):
        with patch.object(_Targets, 'showFullScreen'):
            dialog = _Targets((1000, 800))
        try:
            dialog.resize(1000, 800)
            dialog.ready = True
            measured = []
            dialog.measured.connect(measured.append)
            for x, y in TARGETS:
                dialog.record_sample(x * 1000, y * 800)
            dialog.record_sample(500, 400)
            self.assertEqual(len(measured), 1)
            self.assertEqual(len(measured[0]), 9)
            self.assertFalse(dialog.ready)
        finally:
            dialog.finish()
            dialog.deleteLater()

    def test_applied_preview_cancel_restores_previous_mapping(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(ScreenPage, 'refresh'):
            page = ScreenPage()
            path = Path(folder) / 'screen.json'
            data = {'kind': 'screen', 'backend': 'kde', 'status': 'candidate'}
            save_json(path, data)
            page._transaction = {'path': path, 'data': data, 'changed': True,
                                 'device': {'event': 'event6'}, 'previous': {'matrix': 'old', 'output': 'eDP-1'}}
            with patch('toughbook.screen_gui.screen.KWin') as kwin:
                loop = QEventLoop()
                page.busy_changed.connect(lambda busy: loop.quit() if not busy else None)
                page._set_busy(True)
                page.cancel()
                QTimer.singleShot(5000, loop.quit)
                loop.exec()
                self.assertFalse(page._busy)
                kwin.return_value.restore.assert_called_once()
                self.assertEqual(load_json(path)['status'], 'cancelled')
            page.close()
            page.deleteLater()


if __name__ == '__main__':
    unittest.main()
