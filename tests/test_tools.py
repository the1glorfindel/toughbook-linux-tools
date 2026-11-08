"""Behavior tests with synthetic devices; never touch host configuration. MIT."""
from contextlib import ExitStack
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from toughbook import affine, audio, common, screen

IDENTITY = {'ID_VENDOR_ID': '056a', 'ID_MODEL_ID': '0093', 'ID_USB_INTERFACE_NUM': '01',
            'ID_SERIAL': 'test-unit', 'ID_PATH': 'test-internal-port'}
DEVICE = {'event': 'event47', 'identity': IDENTITY, 'properties': {}}
CARD = {'name': 'alsa_card.test-internal', 'index': 7, 'profile': 'output:analog-stereo',
        'card_serial': 92, 'codec': '10ec0269:ALC269VC'}
SINK = {'name': 'alsa_output.test-internal.analog-stereo', 'card': 92,
        'ports': [{'name': 'analog-output-speaker'}, {'name': 'cf19-output-speaker'}],
        'active_port': 'analog-output-speaker', 'mute': True,
        'volume': {'front-left': {'value': 32100}, 'front-right': {'value': 32100}}}


class TemporaryState(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cf19-tests-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / 'config with spaces'
        self.env = patch.dict(os.environ, {'XDG_CONFIG_HOME': str(self.config),
                                         'XDG_STATE_HOME': str(self.root / 'state with spaces')})
        self.env.start()
        self.addCleanup(self.env.stop)
        capture = __import__("contextlib").redirect_stdout(io.StringIO())
        capture.__enter__()
        self.addCleanup(capture.__exit__, None, None, None)


class AffineTests(unittest.TestCase):
    def test_recovers_scale_offset_and_skew(self):
        samples = [(x*.8+.06, y*.9+.02) for x, y in affine.TARGETS]
        matrix, error = affine.fit(samples, 1024, 768)
        for (x, y), (tx, ty) in zip(samples, affine.TARGETS):
            a,b,c,d,e,f = matrix
            self.assertAlmostEqual(a*x+b*y+c, tx)
            self.assertAlmostEqual(d*x+e*y+f, ty)
        self.assertLess(error, 1e-8)

    def test_composition_applies_old_then_new(self):
        result = affine.compose([2,0,.1, 0,3,-.2], [1,0,.2, 0,1,.4])
        for actual, expected in zip(result, [2,0,.5, 0,3,1.]):
            self.assertAlmostEqual(actual, expected)
        self.assertEqual(affine.from_kwin(','.join(map(str, affine.to_kwin(result)))), result)
        self.assertEqual(affine.to_kwin(result)[2], .5)
        self.assertEqual(affine.to_kwin(result)[3], 0)

    def test_bad_samples_rejected(self):
        for samples in [[(.5,.5)]*9, [(float('nan'), .5)]*9,
                        list(affine.TARGETS[:8]),
                        [(1-x,y) for x,y in affine.TARGETS]]:
            with self.subTest(samples=samples), self.assertRaises(common.ToolError):
                affine.fit(samples, 1024, 768)
        samples = list(affine.TARGETS)
        samples[4] = (.9,.1)
        with self.assertRaises(common.ToolError):
            affine.fit(samples, 1024, 768)

    def test_unsupported_kwin_matrix_rejected(self):
        m = affine.to_kwin(affine.IDENTITY)
        m[15] = 0
        with self.assertRaises(common.ToolError):
            affine.from_kwin(','.join(map(str, m)))


class DiscoveryTests(TemporaryState):
    def test_codec_discovery_does_not_assume_card_zero(self):
        folder = self.root/'card7'
        folder.mkdir()
        (folder/'codec#3').write_text('Codec: Realtek ALC269VC\nVendor Id: 0x10ec0269\n')
        card = {'name': CARD['name'], 'properties': {'api.alsa.card': '7'},
                'index': 92, 'active_profile': CARD['profile']}
        self.assertEqual(audio.devices([card], self.root), [CARD])
        (folder/'codec#3').write_text('Codec: Unrelated codec\n')
        self.assertEqual(audio.devices([card], self.root), [])

    def test_touch_discovery_excludes_pen(self):
        for event in ('event6', 'event99'):
            (self.root/event).mkdir()
        def properties(event):
            return {**IDENTITY, 'ID_INPUT_TOUCHSCREEN': '1' if event=='event99' else '0'}
        with patch.object(common, 'udev_properties', side_effect=properties):
            result = common.touch_devices(self.root)
        self.assertEqual(result[0]['event'], 'event99')
        self.assertEqual(len(result), 1)

    def test_ambiguity_is_not_silently_resolved(self):
        with self.assertRaises(common.ToolError):
            common.choose([DEVICE, DEVICE], 'event')

    def test_missing_dependency_and_command_timeout(self):
        with patch('shutil.which', return_value=None), self.assertRaises(common.ToolError):
            common.require('nonexistent-test-program')
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired('test', 1)), self.assertRaises(common.ToolError):
            common.run('test', timeout=1)

    def test_reject_other_models(self):
        folder = self.root/'class/dmi/id'
        folder.mkdir(parents=True)
        (folder/'product_name').write_text('Other Laptop')
        with self.assertRaises(common.ToolError):
            common.check_model(self.root)


class LayoutTests(unittest.TestCase):
    def test_kde_normal_and_scaled(self):
        output = {'name':'LVDS-1','enabled':True,'rotation':1,'scale':1,
                  'currentModeId':'1','modes':[{'id':'1','size':{'width':1024,'height':768}}]}
        self.assertEqual(screen.kde_layout({'outputs':[output]}), ('LVDS-1',1024,768))
        for outputs in [[output, output], [{**output,'scale':1.25}], [{**output,'rotation':2}]]:
            with self.assertRaises(common.ToolError):
                screen.kde_layout({'outputs':outputs})

    def test_gnome_current_mode_and_scale(self):
        spec = ('eDP-1','TEST','Panel','unit')
        current = (1, [(spec, [('mode',1024,768,60.,1.,[1.],{'is-current':True})],{})],
                   [(0,0,1.,0,True,[spec],{})], {})
        self.assertEqual(screen.gnome_layout(current), ('eDP-1',1024,768))
        scaled = (*current[:2], [(0,0,2.,0,True,[spec],{})], {})
        with self.assertRaises(common.ToolError):
            screen.gnome_layout(scaled)


class WindowTests(unittest.TestCase):
    def window(self):
        window = screen.CalibrationWindow.__new__(screen.CalibrationWindow)
        window.canvas, window.root = Mock(), Mock()
        window.expected, window.size = (1024,768), None
        window.stable, window.ready, window.samples = 0, False, []
        window.started, window.applied = time.monotonic(), False
        window.draw = Mock()
        return window

    def test_waits_for_real_fullscreen(self):
        window = self.window()
        window.canvas.winfo_width.return_value = 200
        window.canvas.winfo_height.return_value = 200
        for _ in range(8):
            window.wait_fullscreen()
        self.assertFalse(window.ready)
        window.draw.assert_not_called()
        window.canvas.winfo_width.return_value = 1024
        window.canvas.winfo_height.return_value = 768
        for _ in range(6):
            window.wait_fullscreen()
        self.assertTrue(window.ready)

    def test_resize_clears_measurements(self):
        window = self.window()
        window.ready, window.size, window.samples = True, (1024,768), [(0,0)]
        window.resize(SimpleNamespace(width=800,height=600))
        self.assertFalse(window.ready)
        self.assertEqual(window.samples, [])

    def test_preview_resize_closes_for_rollback(self):
        window = self.window()
        window.ready, window.applied, window.size = True, True, (1024,768)
        window.resize(SimpleNamespace(width=800,height=600))
        window.root.destroy.assert_called_once()


class ScreenTransactionTests(TemporaryState):
    def test_rule_is_finger_and_port_specific(self):
        text = screen.make_rule(IDENTITY, affine.IDENTITY)
        self.assertIn('ENV{ID_USB_INTERFACE_NUM}=="01"', text)
        self.assertIn('ENV{ID_PATH}=="test-internal-port"', text)
        self.assertIn('1.0 0.0 0.0 0.0 1.0 0.0', text)
        with self.assertRaises(common.ToolError):
            screen.make_rule({**IDENTITY,'ID_USB_INTERFACE_NUM':'00'}, affine.IDENTITY)

    def test_install_refreshes_only_selected_device(self):
        with patch.object(screen,'run') as run, patch.object(screen,'require'):
            screen.install_rule(b'# test\n', DEVICE)
        self.assertIn(('sudo','udevadm','trigger','--action=change','/sys/class/input/event47'),
                      [c.args for c in run.call_args_list])
        self.assertFalse(any('--subsystem-match=input' in c.args for c in run.call_args_list))

    def test_apply_failure_restores_rule(self):
        path = self.root/'candidate.json'
        rule = self.root/'absent-rule'
        common.save_json(path, {'kind':'screen','backend':'gnome','identity':IDENTITY,
                               'previous':{'rule':None},'matrix':affine.IDENTITY,'status':'candidate','size':[1024,768]})
        calls = []
        def install(content, device):
            calls.append(content)
            if content is not None:
                raise common.ToolError('reload failed')
        with patch.object(screen,'RULE',rule), patch.object(screen,'backend_name',return_value='gnome'), \
             patch.object(screen,'find_saved_device',return_value=DEVICE), \
             patch.object(screen,'session_token',return_value='new-session'), \
             patch.object(screen,'layout',return_value=('eDP-1',1024,768)), \
             patch.object(screen,'install_rule',side_effect=install), self.assertRaises(common.ToolError):
            screen.apply_pending(path)
        self.assertIsNone(calls[-1])
        self.assertEqual(common.load_json(path)['status'],'restored')

    def test_kde_cancel_and_error_restore_live_settings(self):
        for fail in (False,True):
            kwin = Mock()
            kwin.get.return_value = {'matrix':','.join(map(str,affine.to_kwin(affine.IDENTITY))),'output':''}
            def window(size, callback):
                def run():
                    callback(affine.IDENTITY,0,affine.TARGETS,size)
                    if fail:
                        raise common.ToolError('GUI error')
                    return False
                return SimpleNamespace(run=run)
            with ExitStack() as stack:
                for name, value in [('desktop_user',Mock()),('check_model',Mock()),('require',Mock()),
                                    ('backend_name',Mock(return_value='kde')),('layout',Mock(return_value=('LVDS-1',1024,768))),
                                    ('touch_devices',Mock(return_value=[DEVICE])),('KWin',Mock(return_value=kwin)),
                                    ('CalibrationWindow',window)]:
                    stack.enter_context(patch.object(screen,name,value))
                if fail:
                    with self.assertRaises(common.ToolError): screen.main([])
                else:
                    self.assertEqual(screen.main([]),2)
                kwin.restore.assert_called_once()


class AudioTransactionTests(TemporaryState):
    def fake_run(self, *args, **kwargs):
        if args[0]=='alsactl' and 'store' in args:
            Path(args[2]).write_text('SYNTHETIC ALSA STATE')
        return SimpleNamespace(stdout='original-default\n',stderr='',returncode=0)

    def test_profile_edit_is_narrow_and_targeted(self):
        system = self.root/'upstream'
        (system/'paths').mkdir(parents=True)
        (system/'profile-sets').mkdir()
        (system/'paths/analog-output-speaker.conf').write_text(
            '# upstream notice\n[Element Headphone]\nswitch = off\nvolume = off\n'
            '[Element Headphone,1]\nswitch = off\nvolume = off\n.include analog-output.conf.common\n')
        (system/'profile-sets/default.conf').write_text('paths-output = analog-output-speaker analog-output-headphones\n')
        files = audio.build_files(self.config,CARD['name'],system)
        texts = list(files.values())
        self.assertIn('# upstream notice',texts[0])
        self.assertIn('[Element Headphone,1]\nswitch = off',texts[0])
        self.assertIn('switch = mute\nvolume = merge',texts[0])
        self.assertIn('analog-output-headphones',texts[1])
        self.assertIn('device.name = "alsa_card.test-internal"',texts[2])
        (system/'paths/analog-output-speaker.conf').write_text('different upstream format')
        with self.assertRaises(common.ToolError):
            audio.build_files(self.config,CARD['name'],system)

    def exercise(self, answers, playback_failure=False, restart_failure=False, interrupted=False):
        paths = audio.audio_paths(self.config)
        paths[2].parent.mkdir(parents=True)
        paths[2].write_text('preexisting user rule\n')
        files = {p:'generated test configuration\n' for p in paths}
        with ExitStack() as stack:
            stack.enter_context(patch.object(audio,'run',side_effect=self.fake_run))
            stack.enter_context(patch.object(audio,'wireplumber_mode',return_value='modern'))
            stack.enter_context(patch.object(audio,'same_device',return_value=CARD))
            stack.enter_context(patch.object(audio,'sink_for',return_value=SINK))
            stack.enter_context(patch.object(audio,'build_files',return_value=files))
            restart = stack.enter_context(patch.object(audio,'restart',return_value=(CARD,SINK)))
            if restart_failure:
                # Installation restart fails, but the recovery restart succeeds.
                restart.side_effect = [common.ToolError('service failed'),(CARD,SINK)]
            play = stack.enter_context(patch.object(audio,'playback'))
            if playback_failure: play.side_effect=common.ToolError('playback failed')
            stack.enter_context(patch.object(audio,'confirm',side_effect=answers))
            stack.enter_context(patch('builtins.input',side_effect=KeyboardInterrupt if interrupted else lambda _:''))
            if interrupted:
                with self.assertRaises(KeyboardInterrupt): audio.repair(CARD)
            elif playback_failure or restart_failure:
                with self.assertRaises(common.ToolError): audio.repair(CARD)
            else:
                result = audio.repair(CARD)
                self.assertEqual(result,0 if answers[:2]==[True,True] else 2)
            if answers[:2]==[True,True] and not (playback_failure or restart_failure or interrupted):
                marker=common.load_json(common.state_dir()/'audio-installed.json')
                first_baseline=marker['baseline']
                audio.repair(CARD)
                self.assertEqual(common.load_json(common.state_dir()/'audio-installed.json')['baseline'],first_baseline)
                audio.restore_backup(first_baseline)
            self.assertFalse(paths[0].exists())
            self.assertFalse(paths[1].exists())
            self.assertEqual(paths[2].read_text(),'preexisting user rule\n')

    def test_negative_first_test_rolls_back(self): self.exercise([False])
    def test_negative_persistent_test_rolls_back(self): self.exercise([True,False])
    def test_playback_error_rolls_back(self): self.exercise([],playback_failure=True)
    def test_service_failure_rolls_back(self): self.exercise([True],restart_failure=True)
    def test_terminal_cancel_rolls_back(self): self.exercise([],interrupted=True)

    def test_repeat_install_keeps_original_baseline(self):
        # Two runs each ask two confirmations.
        with patch.object(audio,'confirm',return_value=True):
            # exercise installs its own mock; supply enough answers for both runs.
            self.exercise([True,True,True,True])

    def test_restore_files_before_reconnecting_to_broken_service(self):
        paths = audio.audio_paths(self.config)
        for path in paths:
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text('bad configuration')
        backup = self.root/'recovery.json'
        common.save_json(backup, {'kind':'audio','config':str(self.config),'device':CARD,
                                 'files':{str(p):None for p in paths},
                                 'sink':{key:SINK[key] for key in ('active_port','volume','mute')},
                                 'default_sink':'previous-default'})
        backup.with_suffix('.alsa-state').write_text('saved mixer')
        def restart(device):
            self.assertTrue(all(not p.exists() for p in paths))
            return CARD,SINK
        with patch.object(audio,'same_device',side_effect=common.ToolError('service unavailable')), \
             patch.object(audio,'restart',side_effect=restart), \
             patch.object(audio,'run',side_effect=self.fake_run):
            audio.restore_backup(backup)
        self.assertEqual(common.load_json(backup)['status'],'restored')

    def test_backup_rejects_unrelated_paths(self):
        with self.assertRaises(common.ToolError):
            common.restore_files({str(self.root/'unrelated'):None},audio.audio_paths(self.config))


if __name__ == '__main__':
    unittest.main()
