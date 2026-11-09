"""Ubuntu package and WirePlumber compatibility checks."""
from pathlib import Path
from types import SimpleNamespace
import os
import tempfile
import unittest
from unittest.mock import patch

from toughbook import audio, common, distro


class WirePlumberTests(unittest.TestCase):
    def test_detects_both_config_formats(self):
        for version, expected in [('wireplumber 0.4.17', 'legacy'),
                                  ('wireplumber 0.5.13', 'modern')]:
            with self.subTest(version=version), patch.object(audio, 'run',
                    return_value=SimpleNamespace(stdout=version)):
                self.assertEqual(audio.wireplumber_mode(), expected)

    def test_legacy_rule_targets_only_selected_card(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            system = root / 'mixer'
            (system / 'paths').mkdir(parents=True)
            (system / 'profile-sets').mkdir()
            (system / 'paths/analog-output-speaker.conf').write_text(
                '[Element Headphone]\nswitch = off\nvolume = off\n')
            (system / 'profile-sets/default.conf').write_text(
                'analog-output-speaker\n')
            files = audio.build_files(root / 'config', 'alsa_card.test', system,
                                      mode='legacy')
            rule_path = next(p for p in files if p.suffix == '.lua')
            self.assertIn('main.lua.d', str(rule_path))
            self.assertIn('"device.name", "equals", "alsa_card.test"', files[rule_path])
            self.assertIn('["device.profile-set"] = "cf19.conf"', files[rule_path])

    def test_legacy_backup_restores_exact_files(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ,
                {'XDG_CONFIG_HOME': str(Path(folder) / 'config'),
                 'XDG_STATE_HOME': str(Path(folder) / 'state')}):
            config = common.config_dir()
            paths = audio.audio_paths(config, 'legacy')
            paths[2].parent.mkdir(parents=True)
            paths[2].write_text('changed rule')
            backup = Path(folder) / 'audio.json'
            common.save_json(backup, {
                'kind': 'audio', 'config': str(config),
                'device': {'name': 'alsa_card.test', 'codec': 'test'},
                'files': {str(path): None for path in paths},
                'sink': {'active_port': None, 'volume': {}, 'mute': False},
                'default_sink': 'test',
            })
            backup.with_suffix('.alsa-state').write_text('saved mixer')
            with patch.object(audio, 'restart', return_value=(
                    {'index': 7}, {'name': 'test'})), \
                 patch.object(audio, 'restore_routing'), \
                 patch.object(audio, 'run'):
                audio.restore_backup(backup, remove_marker=False)
            self.assertFalse(paths[2].exists())


if __name__ == '__main__':
    unittest.main()
