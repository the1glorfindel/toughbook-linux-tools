"""Portable driver decoding and source packaging. SPDX-License-Identifier: MIT"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DriverTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('cc'), 'C compiler is not installed; decoder execution pending')
    def test_actual_decoder_press_release_and_unknown_vectors(self):
        with tempfile.TemporaryDirectory() as folder:
            program = Path(folder)/'decode'
            subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',
                '-o',str(program),str(ROOT/'driver/test-hbtn-decode.c')],check=True,capture_output=True)
            subprocess.run([str(program)],check=True,timeout=10)

    def test_install_uninstall_shell_syntax(self):
        subprocess.run(['bash','-n',str(ROOT/'driver/install.sh'),str(ROOT/'driver/uninstall.sh')],check=True)

    @unittest.skipUnless(shutil.which('udevadm'), 'systemd udev tools unavailable')
    def test_narrow_rule_syntax(self):
        subprocess.run(['udevadm','verify',str(ROOT/'driver/70-panasonic-hbtn.rules')],
                       check=True,capture_output=True)

if __name__ == '__main__': unittest.main()
