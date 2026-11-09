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

    def test_resize_during_apply_or_preview_requests_recovery(self):
        for preview in (False, True):
            with patch.object(_Targets, 'showFullScreen'):
                dialog = _Targets((1000, 800))
            try:
                dialog.resize(1000, 800)
                dialog.samples = list(TARGETS)
                dialog.ready = False
                dialog.preview = preview
                cancelled = []
                dialog.cancelled.connect(lambda: cancelled.append(True))
                dialog.resize(800, 600)
                # A hidden widget receives its resize event when first shown.
                from PySide6.QtGui import QResizeEvent
                from PySide6.QtCore import QSize
                dialog.resizeEvent(QResizeEvent(QSize(800, 600), QSize(1000, 800)))
                self.assertTrue(cancelled)
            finally:
                dialog.finish()
                dialog.deleteLater()

    def test_native_verification_accepts_actual_samples_and_rejects_large_error(self):
        from toughbook import screen_gui
        from toughbook.common import ToolError
        for bad in (False, True):
            samples = list(TARGETS)
            if bad:
                samples[0] = (.5, .5)
            with patch.object(screen_gui, 'QApplication') as application, \
                 patch.object(screen_gui, '_Targets') as targets, patch('signal.signal'):
                dialog = targets.return_value
                def run():
                    dialog.measured.connect.call_args.args[0](samples)
                    if not bad:
                        dialog.accepted_result.connect.call_args.args[0]()
                application.instance.return_value.exec.side_effect = run
                if bad:
                    with self.assertRaisesRegex(ToolError, 'missed targets'):
                        screen_gui.verify_targets((1000, 800))
                else:
                    self.assertTrue(screen_gui.verify_targets((1000, 800)))

    def test_generic_measurement_saves_candidate_without_live_mutation(self):
        from toughbook.affine import IDENTITY
        with tempfile.TemporaryDirectory() as folder, patch.object(ScreenPage, 'refresh'):
            page = ScreenPage()
            path = Path(folder) / 'screen.json'
            data = {'kind': 'screen', 'backend': 'libinput', 'status': 'measuring'}
            page._transaction = {'backend': 'libinput', 'path': path, 'data': data,
                                 'size': (1000, 800), 'old': IDENTITY, 'changed': False}
            with patch.object(_Targets, 'showFullScreen'):
                page._dialog = _Targets((1000, 800), page)
            page._busy = True
            with patch('toughbook.screen_gui.screen.KWin') as kwin, \
                 patch('toughbook.screen_gui.screen.XInput') as xinput:
                page._measured(list(TARGETS))
                self.assertEqual(load_json(path)['status'], 'candidate')
                self.assertFalse(page._transaction['changed'])
                self.assertIn('Save', page._dialog.keep.text())
                page._keep()
                self.assertEqual(load_json(path)['status'], 'candidate')
                kwin.assert_not_called()
                xinput.assert_not_called()
            page.close()
            page.deleteLater()

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
