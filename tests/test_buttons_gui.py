"""Qt assignment controls. SPDX-License-Identifier: MIT"""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication

from toughbook import buttons
from toughbook.buttons_gui import ButtonsPage


APP = QApplication.instance() or QApplication([])


class ButtonPageTests(unittest.TestCase):
    def test_assignments_use_selected_action_and_installed_app(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'XDG_CONFIG_HOME': str(Path(folder) / 'config')}), \
             patch.object(ButtonsPage, 'refresh_status'), \
             patch.object(ButtonsPage, 'app_choices', return_value=[('org.example.App.desktop', 'Example App')]):
            page = ButtonsPage()
            try:
                self.assertEqual(page.gather(), buttons.defaults())
                page.kind['circle'].setCurrentIndex(page.kind['circle'].findData('application'))
                page.app_choice['circle'].setCurrentIndex(0)
                page.save_settings()
                self.assertEqual(buttons.load_settings()['circle'],
                                 {'type': 'application', 'value': 'org.example.App.desktop'})
                page.reset_settings()
                self.assertEqual(buttons.load_settings(), buttons.defaults())
            finally:
                page.timer.stop()
                page.close()
                page.deleteLater()
                APP.sendPostedEvents(None, QEvent.DeferredDelete)


if __name__ == '__main__':
    unittest.main()
