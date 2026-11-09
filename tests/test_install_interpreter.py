"""Source installation interpreter selection and preflight failure behavior."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from toughbook import integration
from toughbook.common import ToolError


class InterpreterTests(unittest.TestCase):
    def test_button_install_reenters_before_writing_helper_commands(self):
        from toughbook import buttons
        with patch.object(integration.runtime, 'frozen', return_value=False), \
             patch.object(integration, 'source_interpreter', return_value='/managed/bin/python'), \
             patch.object(buttons.runtime, 'host_run') as run, \
             patch.object(integration, 'install_app') as install, \
             patch.object(buttons, 'write_autostart') as autostart:
            buttons.integration(True)
            run.assert_called_once_with(
                ['/managed/bin/python', str(integration.runtime.application_root()/'toughbook-buttons.py'),
                 '--install'], check=True)
            install.assert_not_called()
            autostart.assert_not_called()

    def test_keeps_current_interpreter_when_all_gui_imports_work(self):
        with patch.object(integration.importlib, 'import_module') as load:
            self.assertEqual(integration.source_interpreter(), sys.executable)
        self.assertEqual([call.args[0] for call in load.call_args_list], list(integration.GUI_IMPORTS))

    def test_managed_environment_is_probed_and_selected(self):
        with tempfile.TemporaryDirectory() as folder, \
             patch.dict(os.environ, {'XDG_DATA_HOME': folder}), \
             patch.object(integration.importlib, 'import_module', side_effect=ImportError), \
             patch.object(integration.subprocess, 'run', return_value=Mock(returncode=0)) as run:
            candidate = Path(folder)/'toughbook-tools-python/bin/python'
            candidate.parent.mkdir(parents=True)
            candidate.touch()
            self.assertEqual(integration.source_interpreter(), str(candidate))
            command = run.call_args.args[0]
            self.assertEqual(command[:2], [str(candidate), '-c'])
            for module in integration.GUI_IMPORTS:
                self.assertIn('import ' + module, command[2])

    def test_failed_or_timed_out_probe_reports_setup_instruction(self):
        with tempfile.TemporaryDirectory() as folder, \
             patch.dict(os.environ, {'XDG_DATA_HOME': folder}), \
             patch.object(integration.importlib, 'import_module', side_effect=ImportError):
            candidate = Path(folder)/'toughbook-tools-python/bin/python'
            candidate.parent.mkdir(parents=True)
            candidate.touch()
            for result in (Mock(returncode=1), subprocess.TimeoutExpired('python', 20)):
                with self.subTest(result=result), patch.object(integration.subprocess, 'run') as run:
                    if isinstance(result, Exception):
                        run.side_effect = result
                    else:
                        run.return_value = result
                    with self.assertRaisesRegex(ToolError, 'setup-linux.py'):
                        integration.source_interpreter()

    def test_reentry_precedes_any_installation_mutation(self):
        with patch.object(integration, 'desktop_user'), \
             patch.object(integration.runtime, 'frozen', return_value=False), \
             patch.object(integration, 'source_interpreter', return_value='/managed/bin/python'), \
             patch.object(integration.subprocess, 'run') as run, \
             patch.object(integration.shutil, 'copytree') as copy:
            integration.install_app('buttons')
            run.assert_called_once_with(
                ['/managed/bin/python', str(integration.runtime.application_root()/'toughbook-tools.py'),
                 '--install', '--page', 'buttons'], check=True)
            copy.assert_not_called()

    def test_missing_dependencies_leave_installation_untouched(self):
        with patch.object(integration, 'desktop_user'), \
             patch.object(integration.runtime, 'frozen', return_value=False), \
             patch.object(integration, 'source_interpreter', side_effect=ToolError('setup required')), \
             patch.object(integration.subprocess, 'run') as run, \
             patch.object(integration.shutil, 'copytree') as copy:
            with self.assertRaises(ToolError):
                integration.install_app()
            run.assert_not_called()
            copy.assert_not_called()
