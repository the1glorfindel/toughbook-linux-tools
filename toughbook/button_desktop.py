"""Desktop button actions for KDE and GNOME Wayland sessions. SPDX-License-Identifier: MIT"""
import json
import os
import tempfile

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
    if os.environ.get('XDG_SESSION_TYPE') != 'wayland':
        raise ToolError('Desktop button actions require a KDE or GNOME Wayland session.')
    desktop = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
    if 'kde' in desktop or 'plasma' in desktop:
        return 'kde'
    if 'gnome' in desktop:
        return 'gnome'
    raise ToolError('Supported desktops are KDE Plasma and GNOME on Wayland.')


def _lock():
    dbus = dbus_module()
    bus = dbus.SessionBus()
    if os.environ.get('XDG_CURRENT_DESKTOP', '').lower().find('gnome') >= 0:
        try:
            bus.get_object('org.gnome.ScreenSaver', '/org/gnome/ScreenSaver').Lock()
            return
        except Exception:
            pass
    try:
        bus.get_object('org.freedesktop.ScreenSaver', '/org/freedesktop/ScreenSaver').Lock()
    except Exception as exc:
        raise ToolError(f'Could not lock the session: {exc}') from exc


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
            if isinstance(exc, ToolError):
                raise
            raise ToolError(f'Could not toggle the KDE virtual keyboard: {exc}') from exc
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
    """Perform a named hardware-button action in the current Wayland session."""
    action = str(action).lower()
    if action not in ('keyboard', 'launcher', 'lock', 'rotate'):
        raise ToolError(f'Unknown desktop button action: {action}')
    backend = backend_name()
    if action == 'keyboard':
        _keyboard(backend)
    elif action == 'launcher':
        # Invoke the desktop's standard application launcher.
        if backend == 'kde':
            dbus = dbus_module()
            try:
                dbus.SessionBus().get_object('org.kde.plasmashell', '/PlasmaShell').activateLauncherMenu()
            except Exception as exc:
                raise ToolError(f'Could not open the KDE application launcher: {exc}') from exc
        else:
            # GNOME exposes application search through the standard Overview
            # command on supported installations; no Shell Eval interface used.
            dbus = dbus_module()
            try:
                shell = dbus.SessionBus().get_object('org.gnome.Shell', '/org/gnome/Shell')
                dbus.Interface(shell, 'org.gnome.Shell').FocusSearch()
            except Exception as exc:
                raise ToolError(f'Could not open the GNOME application launcher: {exc}') from exc
    elif action == 'lock':
        _lock()
    elif backend == 'kde':
        _rotate_kde()
    else:
        _rotate_gnome()

