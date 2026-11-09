"""Capability-based desktop button actions for Wayland and X11. SPDX-License-Identifier: MIT"""
import json
import os
import tempfile
import re
import shutil
import shlex
import subprocess

from . import session, runtime

from .common import ToolError, require, run, state_dir


MUTTER = 'org.gnome.Mutter.DisplayConfig'
MUTTER_PATH = '/org/gnome/Mutter/DisplayConfig'


def dbus_module():
    """Import dbus-python only for actions which need the session bus."""
    try:
        import dbus
        return dbus
    except ImportError as exc:
        raise ToolError('Install python3-dbus to use desktop button actions.') from exc


def backend_name():
    return session.compositor()


def _lock():
    dbus = dbus_module()
    bus = dbus.SessionBus()
    for service, path in (('org.freedesktop.ScreenSaver', '/org/freedesktop/ScreenSaver'),
                          ('org.gnome.ScreenSaver', '/org/gnome/ScreenSaver'),
                          ('org.cinnamon.ScreenSaver', '/org/cinnamon/ScreenSaver'),
                          ('org.mate.ScreenSaver', '/org/mate/ScreenSaver')):
        try:
            dbus.Interface(bus.get_object(service, path), service).Lock(timeout=10)
            return
        except Exception:
            pass
    try:
        props = session.login_session()
        run('loginctl', 'lock-session', props['Id'])
    except Exception as exc:
        raise ToolError(f'No session lock interface is available: {exc}. Assign your desktop locker command.') from exc


_keyboard_process = None


def _spawn_available(commands, purpose, independent=False):
    for command in commands:
        if shutil.which(command[0]):
            if independent:
                from .buttons import execute
                execute({'type': 'command', 'value': shlex.join(command)})
                return None
            return runtime.host_popen(command, start_new_session=True)
    raise ToolError(f'No compatible {purpose} is installed. Assign its executable in the button settings.')


def _portable_keyboard(backend):
    global _keyboard_process
    if _keyboard_process is not None and _keyboard_process.poll() is None:
        _keyboard_process.terminate()
        return
    commands = [['onboard'], ['matchbox-keyboard']] if backend == 'x11' else [['wvkbd-mobintl'], ['wvkbd']]
    _keyboard_process = _spawn_available(commands, 'on-screen keyboard')


def _launcher(backend):
    if backend in ('kde', 'gnome'):
        try:
            dbus = dbus_module()
            if backend == 'kde':
                dbus.SessionBus().get_object('org.kde.plasmashell', '/PlasmaShell').activateLauncherMenu(timeout=10)
            else:
                obj = dbus.SessionBus().get_object('org.gnome.Shell', '/org/gnome/Shell')
                dbus.Interface(obj, 'org.gnome.Shell').FocusSearch(timeout=10)
            return
        except Exception:
            pass
    commands = ([['fuzzel'], ['wofi', '--show', 'drun']] if backend != 'x11' else [])
    commands += [['rofi', '-show', 'drun'], ['xfce4-appfinder'], ['mate-panel', '--run-dialog'], ['lxqt-runner']]
    _spawn_available(commands, 'application launcher', independent=True)


def _keyboard(backend):
    if backend == 'kde':
        dbus = dbus_module()
        try:
            obj = dbus.SessionBus().get_object('org.kde.KWin', '/VirtualKeyboard')
            props = dbus.Interface(obj, 'org.freedesktop.DBus.Properties')
            iface = 'org.kde.kwin.VirtualKeyboard'
            if not bool(props.Get(iface, 'available', timeout=10)):
                raise ToolError('KDE reports that no virtual keyboard is available.')
            visible = bool(props.Get(iface, 'visible', timeout=10))
            if visible:
                props.Set(iface, 'active', False, timeout=10)
            else:
                dbus.Interface(obj, iface).forceActivate(timeout=10)
        except Exception as exc:
            _portable_keyboard(backend)
            return
        return
    if backend != 'gnome':
        _portable_keyboard(backend)
        return
    require('gsettings')
    current = run('gsettings', 'get', 'org.gnome.desktop.a11y.applications',
                  'screen-keyboard-enabled').stdout.strip()
    if current not in ('true', 'false'):
        raise ToolError('GNOME returned an invalid screen keyboard setting.')
    run('gsettings', 'set', 'org.gnome.desktop.a11y.applications',
        'screen-keyboard-enabled', 'false' if current == 'true' else 'true')


def _internal_kde_output():
    require('kscreen-doctor')
    try:
        outputs = json.loads(run('kscreen-doctor', '-j').stdout)['outputs']
    except (ValueError, KeyError, TypeError) as exc:
        raise ToolError('Could not read the KDE display configuration.') from exc
    active = [o for o in outputs if o.get('enabled')]
    internal = [o for o in active if str(o.get('name', '')).startswith(('LVDS', 'eDP', 'DSI'))]
    if len(active) != 1 or len(internal) != 1:
        raise ToolError('Rotation is available only when the internal display is the sole active display.')
    return internal[0]


def _rotate_kde():
    output = _internal_kde_output()
    name = output['name']
    old = output.get('rotation', 1)
    # KScreen JSON uses 1/2/4/8; its command accepts named orientations.
    values = (1, 8, 4, 2)
    names = {1: 'normal', 2: 'left', 4: 'inverted', 8: 'right'}
    try:
        idx = values.index(int(old))
    except (ValueError, TypeError):
        raise ToolError('The current KDE rotation is not recognized.')
    next_value = values[(idx + 1) % len(values)]
    try:
        _save_recovery({'backend': 'kde', 'output': output})
    except OSError:
        pass
    try:
        run('kscreen-doctor', f'output.{name}.rotation.{names[next_value]}')
        applied = _internal_kde_output()
        if applied['name'] != name or int(applied.get('rotation', -1)) != next_value:
            raise ToolError('KDE did not apply the requested rotation.')
    except Exception as exc:
        try:
            run('kscreen-doctor', f'output.{name}.rotation.{names[int(old)]}')
            restored = _internal_kde_output()
            if restored['name'] != name or int(restored.get('rotation', -1)) != int(old):
                raise ToolError('KDE did not restore the previous rotation.')
        except Exception as restore_exc:
            raise ToolError(f'Rotation failed ({exc}); restoring the previous display configuration also failed ({restore_exc}). Use Display Settings or the saved recovery snapshot.') from exc
        raise ToolError(f'Rotation failed ({exc}); the previous rotation was restored.') from exc


def _gnome_state():
    dbus = dbus_module()
    bus = dbus.SessionBus()
    obj = bus.get_object(MUTTER, MUTTER_PATH)
    return dbus, dbus.Interface(obj, MUTTER).GetCurrentState(timeout=10), obj


def _rotate_gnome():
    dbus, state, obj = _gnome_state()
    serial, monitors, logical, properties = state
    active = [item for item in logical]
    internal = [item for item in active if len(item[5]) == 1 and
                str(item[5][0][0]).startswith(('LVDS', 'eDP', 'DSI'))]
    if len(active) != 1 or len(internal) != 1:
        raise ToolError('Rotation is available only when the internal display is the sole active display.')
    x, y, scale, transform, primary, specs, props = internal[0]
    if int(transform) not in (0, 1, 2, 3):
        raise ToolError("Disable reflected display transforms before rotating.")
    next_transform = (int(transform) + 1) % 4
    # ApplyMonitorsConfig uses per-output connector/mode/properties tuples,
    # whereas GetCurrentState exposes monitor specs plus the currently active
    # mode. Reconstruct the former while preserving each mode and placement.
    monitor_configs = []
    for spec in specs:
        monitor = next((item for item in monitors if tuple(item[0]) == tuple(spec)), None)
        if monitor is None:
            raise ToolError(f'Could not identify the active mode for {spec[0]}.')
        current_modes = [mode for mode in monitor[1] if mode[-1].get('is-current', False)]
        if len(current_modes) != 1:
            raise ToolError(f'Could not identify the active mode for {spec[0]}.')
        output_props = {}
        if 'is-underscanning' in monitor[2]:
            output_props['underscanning'] = bool(monitor[2]['is-underscanning'])
        if 'color-mode' in monitor[2]:
            output_props['color-mode'] = monitor[2]['color-mode']
        monitor_configs.append((str(spec[0]), str(current_modes[0][0]), output_props))
    config_properties = {}
    if properties.get('supports-changing-layout-mode'):
        config_properties['layout-mode'] = properties.get('layout-mode', 1)
    updated = [(x, y, scale, next_transform, primary, monitor_configs)]
    # Use Mutter's documented transactional API; retain every output, mode,
    # scale, position and logical-monitor property from the live configuration.
    iface = dbus.Interface(obj, MUTTER)
    snapshot = [(x, y, scale, int(transform), primary, monitor_configs)]
    try:
        _save_recovery({'backend': 'gnome', 'state': state})
    except OSError:
        pass
    try:
        iface.ApplyMonitorsConfig(serial, 1, updated, config_properties, timeout=20)
        applied = iface.GetCurrentState(timeout=10)
        current = [item for item in applied[2] if len(item[5]) == 1 and
                   str(item[5][0][0]).startswith(('LVDS', 'eDP', 'DSI'))]
        if len(applied[2]) != 1 or len(current) != 1 or int(current[0][3]) != next_transform:
            raise ToolError('Mutter did not apply the requested display rotation.')
    except Exception as exc:
        try:
            fresh = iface.GetCurrentState(timeout=10)
            iface.ApplyMonitorsConfig(fresh[0], 1, snapshot, config_properties, timeout=20)
            restored = iface.GetCurrentState(timeout=10)
            if len(restored[2]) != 1 or int(restored[2][0][3]) != int(transform):
                raise ToolError('Mutter did not restore the previous display rotation.')
        except Exception as restore_exc:
            raise ToolError(f'Rotation failed ({exc}); restoring the previous display configuration also failed ({restore_exc}).') from exc
        raise ToolError(f'Could not rotate the internal display: {exc}') from exc


def _save_recovery(data):
    """Write a best-effort atomic diagnostic/recovery snapshot without partial files."""
    folder = state_dir() / 'button-desktop'
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = folder / 'display-recovery.json'
    fd, temp_name = tempfile.mkstemp(prefix='.display-', dir=folder)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, default=lambda value: list(value) if isinstance(value, tuple) else str(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def perform(action):
    """Perform a named action through the active graphical session capabilities."""
    action = str(action).lower()
    if action not in ('keyboard', 'launcher', 'lock', 'rotate'):
        raise ToolError(f'Unknown desktop button action: {action}')
    backend = backend_name()
    if action == 'keyboard':
        _keyboard(backend)
    elif action == 'launcher':
        _launcher(backend)
    elif action == 'lock':
        _lock()
    elif backend == 'kde':
        _rotate_kde()
    elif backend == 'gnome':
        _rotate_gnome()
    elif backend == 'x11':
        _rotate_x11()
    else:
        _rotate_wlr()


X11_ROTATIONS = {
    'normal': [1., 0., 0., 0., 1., 0.],
    'right': [0., 1., 0., -1., 0., 1.],
    'inverted': [-1., 0., 1., 0., -1., 1.],
    'left': [0., -1., 1., 1., 0., 0.],
}


def _x11_output():
    require('xrandr')
    outputs = []
    for line in run('xrandr', '--query').stdout.splitlines():
        match = re.match(r'^(\S+) connected(?: primary)? (\d+)x(\d+)[+-]\d+[+-]\d+(?: (normal|left|right|inverted))? ', line)
        if match:
            tail = line[match.end():].split('(', 1)[0].strip()
            if tail:
                raise ToolError('Disable reflected X11 transforms before rotating.')
            outputs.append({'name': match[1], 'rotation': match[4] or 'normal'})
    if len(outputs) != 1 or not outputs[0]['name'].startswith(('LVDS', 'eDP', 'DSI')):
        raise ToolError('Rotation requires the internal display as the sole active output.')
    return outputs[0]


def _rotate_x11():
    from .affine import compose
    from .common import choose, touch_devices
    from .xinput import XInput
    output = _x11_output()
    old = output['rotation']
    order = ('normal', 'right', 'inverted', 'left')
    new = order[(order.index(old) + 1) % 4]
    touch = XInput(choose(touch_devices(), 'event'))
    previous = touch.get()
    # Remove the old orthogonal output transform before composing the new one.
    inverse = X11_ROTATIONS[{'normal': 'normal', 'right': 'left', 'left': 'right', 'inverted': 'inverted'}[old]]
    matrix = compose(X11_ROTATIONS[new], compose(inverse, previous['matrix']))
    _save_recovery({'backend': 'x11', 'output': output, 'touch': previous})
    try:
        run('xrandr', '--output', output['name'], '--rotate', new)
        touch.set(matrix)
        if _x11_output() != {'name': output['name'], 'rotation': new}:
            raise ToolError('X11 did not apply the requested rotation.')
    except Exception as exc:
        failures = []
        def restore_output():
            run('xrandr', '--output', output['name'], '--rotate', old)
            if _x11_output() != output:
                raise ToolError('X11 did not restore the previous orientation.')
        for restore in (restore_output, lambda: touch.restore(previous)):
            try:
                restore()
            except Exception as failure:
                failures.append(str(failure))
        raise ToolError(f'Rotation failed: {exc}. ' + ('Recovery needs attention: ' + '; '.join(failures)
                        if failures else 'Previous display and touch mapping restored.')) from exc


def _wlr_output():
    require('wlr-randr')
    outputs = json.loads(run('wlr-randr', '--json').stdout)
    active = [o for o in outputs if o.get('enabled')]
    if len(active) != 1 or not active[0]['name'].startswith(('LVDS', 'eDP', 'DSI')):
        raise ToolError('Rotation requires the internal display as the sole active output.')
    return active[0]


def _rotate_wlr():
    try:
        output = _wlr_output()
    except Exception as exc:
        raise ToolError(f'This compositor does not expose supported output management: {exc}. '
                        'Assign its rotation command in the button settings.') from exc
    order = ('normal', '90', '180', '270')
    old = str(output.get('transform', 'normal'))
    if old not in order:
        raise ToolError('Disable reflected output transforms before rotating.')
    new = order[(order.index(old) + 1) % 4]
    _save_recovery({'backend': 'wlr', 'output': output})
    try:
        run('wlr-randr', '--output', output['name'], '--transform', new)
        actual = _wlr_output()
        if actual['name'] != output['name'] or str(actual['transform']) != new:
            raise ToolError('The compositor did not apply rotation.')
    except Exception as exc:
        try:
            run('wlr-randr', '--output', output['name'], '--transform', old)
            actual = _wlr_output()
            if actual['name'] != output['name'] or str(actual['transform']) != old:
                raise ToolError('The compositor did not restore rotation.')
        except Exception as failure:
            raise ToolError(f'Rotation failed ({exc}); recovery needs attention ({failure}).') from exc
        raise ToolError(f'Rotation failed ({exc}); previous orientation restored.') from exc
