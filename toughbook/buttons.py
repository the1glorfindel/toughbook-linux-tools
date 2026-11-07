"""User-session tablet button settings. SPDX-License-Identifier: MIT"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import uuid

from .common import ToolError, config_dir, state_dir, save_json, desktop_user

BUTTONS = {'keyboard': ('Keyboard', 'On-screen keyboard', 'F13', 'keyboard'),
           'circle': ('Circle', 'Panasonic dashboard/application', 'F14', 'launcher'),
           'rotation': ('Rotation', 'Rotate display', 'F15', 'rotate'),
           'key': ('Key', 'Windows security / Ctrl+Alt+Delete', 'F16', 'lock')}
# Fedora's default evdev XKB map translates these Linux F-key codes to XF86 keysyms.
# The kernel still emits F13-F16; portal triggers use desktop keysyms.
TRIGGERS = dict(zip(BUTTONS, ('XF86Tools', 'XF86Launch5', 'XF86Launch6', 'XF86Launch7')))
BUILTINS = ('keyboard', 'launcher', 'rotate', 'lock', 'disabled')
APP_ID = 'org.toughbook.Buttons'
CONTROL_PATH = '/org/toughbook/Buttons/Helper'
CONTROL_IFACE = APP_ID + '.Helper'


def defaults():
    return {key: {'type': 'builtin', 'value': row[3]} for key, row in BUTTONS.items()}


def settings_path():
    return config_dir() / 'toughbook-buttons/settings.json'


def validate(settings):
    if not isinstance(settings, dict) or set(settings) != set(BUTTONS):
        raise ToolError('Settings must contain exactly the four tablet buttons. Reset defaults in the app.')
    for assignment in settings.values():
        if not isinstance(assignment, dict) or set(assignment) != {'type', 'value'}:
            raise ToolError('Invalid button assignment.')
        kind, value = assignment['type'], assignment['value']
        if not isinstance(value, str):
            raise ToolError('Assignment value must be text.')
        if kind == 'builtin' and value in BUILTINS:
            continue
        if kind == 'command':
            if not shlex.split(value):
                raise ToolError('Enter an executable and optional arguments.')
        elif kind == 'shell':
            if not value.strip():
                raise ToolError('Shell command is empty.')
        elif kind == 'application':
            if not value or '/' in value or not value.endswith('.desktop'):
                raise ToolError('Choose an installed desktop application.')
        else:
            raise ToolError('Unknown assignment type or built-in action.')
    return settings


def load_settings():
    path = settings_path()
    return validate(json.loads(path.read_text())) if path.exists() else defaults()


def execute(assignment):
    kind, value = assignment['type'], assignment['value']
    if kind == 'builtin':
        if value != 'disabled':
            from .button_desktop import perform
            perform(value)
        return
    if kind == 'application':
        from gi.repository import Gio
        app = Gio.DesktopAppInfo.new(value)
        if app is None:
            raise ToolError(f'Application {value} is missing; choose another in Toughbook Buttons.')
        argv = ['gio', 'launch', app.get_filename()]
    else:
        argv = ['/bin/sh', '-c', value] if kind == 'shell' else shlex.split(value)
    if not shutil.which(argv[0]):
        raise ToolError(f'Executable {argv[0]} is missing. Edit this assignment.')
    # Launch asynchronously, but reap and report nonzero exits through the GLib loop.
    from gi.repository import GLib
    if not shutil.which('systemd-run'):
        raise ToolError('Missing systemd-run; install Fedora systemd to launch independent application scopes.')
    scoped = ['systemd-run', '--user', '--scope', '--quiet', '--collect', '--', *argv]
    process = subprocess.Popen(scoped, start_new_session=True)
    def finished():
        code = process.poll()
        if code is None:
            return True
        if code:
            record_status(error=f'{argv[0]} exited with status {code}')
        return False
    GLib.timeout_add(250, finished)


def devices(root=Path('/sys/class/input')):
    result = []
    for event in sorted(root.glob('event*')):
        try:
            dev = event / 'device'
            # Only our dedicated driver, never the ordinary keyboard.
            if (dev / 'name').read_text().strip() != 'Panasonic CF-19 Tablet Buttons':
                continue
            if 'MAT001F' not in str(dev.resolve()):
                continue
            result.append('/dev/input/' + event.name)
        except OSError:
            continue
    return result


def record_status(**data):
    path = state_dir() / 'buttons-session.json'
    previous = json.loads(path.read_text()) if path.exists() else {}
    previous.update(data)
    save_json(path, previous)


def portal_status():
    try:
        import dbus
        bus = dbus.SessionBus()
        obj = bus.get_object('org.freedesktop.portal.Desktop', '/org/freedesktop/portal/desktop')
        version = dbus.Interface(obj, 'org.freedesktop.DBus.Properties').Get(
            'org.freedesktop.portal.GlobalShortcuts', 'version', timeout=5)
        return f'Global Shortcuts portal v{version} advertised; binding requires backend approval'
    except Exception as exc:
        return f'Global Shortcuts unavailable: {exc}. Install the desktop portal backend and log in again.'


class Portal:
    """Keep the D-Bus connection and portal session alive for the helper's lifetime."""
    def __init__(self):
        import dbus
        from dbus.mainloop.glib import DBusGMainLoop
        DBusGMainLoop(set_as_default=True)
        self.dbus = dbus
        self.bus = dbus.SessionBus(private=True)
        self.obj = self.bus.get_object('org.freedesktop.portal.Desktop', '/org/freedesktop/portal/desktop')
        self.api = dbus.Interface(self.obj, 'org.freedesktop.portal.GlobalShortcuts')
        self.session = None
        self.active = set()
        self.pending = []
        self.session_matches = []
        self.shortcuts = {}
        self.bus.add_signal_receiver(self.owner_changed, signal_name='NameOwnerChanged',
            dbus_interface='org.freedesktop.DBus', bus_name='org.freedesktop.DBus',
            arg0='org.freedesktop.portal.Desktop')
        self.register_host()
        self.portal_owner = str(self.bus.get_name_owner('org.freedesktop.portal.Desktop'))

    def register_host(self):
        # Must precede all portal calls on this connection (portal >= 1.20).
        try:
            self.dbus.Interface(self.obj, 'org.freedesktop.host.portal.Registry').Register(
                APP_ID, self.dbus.Dictionary({}, signature='sv'), timeout=10)
        except self.dbus.DBusException as exc:
            if exc.get_dbus_name() not in ('org.freedesktop.DBus.Error.UnknownMethod',
                                           'org.freedesktop.DBus.Error.UnknownInterface'):
                raise ToolError(f'Cannot register portal application identity: {exc}') from exc
            # Older portals may permit host callers without explicit registration.

    def clear_requests(self):
        from gi.repository import GLib
        for pending in self.pending[:]:
            pending['match'].remove()
            if pending['timer'] is not None:
                GLib.source_remove(pending['timer'])
        self.pending.clear()

    def clear_session_signals(self):
        for match in self.session_matches:
            match.remove()
        self.session_matches.clear()

    def owner_changed(self, name, previous, owner):
        if str(owner) == getattr(self, 'portal_owner', None):
            return
        self.portal_owner = str(owner)
        self.clear_requests()
        self.clear_session_signals()
        self.active.clear()
        self.session = None
        self.shortcuts = {}
        record_status(shortcuts={}, error='Portal restarted; reconnecting…')
        if owner:
            try:
                self.obj = self.bus.get_object('org.freedesktop.portal.Desktop', '/org/freedesktop/portal/desktop')
                self.api = self.dbus.Interface(self.obj, 'org.freedesktop.portal.GlobalShortcuts')
                self.register_host()
                self.start()
            except Exception as exc:
                record_status(error=f'Portal reconnection failed: {exc}. Restart the helper.')

    def request(self, method, args, callback, extra=None):
        token = 'tb' + uuid.uuid4().hex
        sender = self.bus.get_unique_name()[1:].replace('.', '_')
        path = f'/org/freedesktop/portal/desktop/request/{sender}/{token}'
        options = self.dbus.Dictionary({'handle_token': token, **(extra or {})}, signature='sv')
        from gi.repository import GLib
        pending = {'match': None, 'timer': None}
        def cleanup():
            if pending not in self.pending:
                return
            self.pending.remove(pending)
            pending['match'].remove()
            if pending['timer'] is not None:
                GLib.source_remove(pending['timer'])
        def timed_out():
            pending['timer'] = None
            cleanup()
            record_status(error="Portal approval timed out. Restart the helper and approve its dialog.")
            return False
        def response(code, results):
            cleanup()
            if int(code):
                record_status(error=f'Portal request denied/cancelled (code {code}); open desktop shortcut settings and resolve conflicts.')
                return
            try:
                callback(results)
            except Exception as exc:
                record_status(error=f'Portal setup failed: {exc}. Restart the helper.')
        pending['match'] = self.bus.add_signal_receiver(response, signal_name='Response',
                 dbus_interface='org.freedesktop.portal.Request', path=path,
                 bus_name='org.freedesktop.portal.Desktop')
        pending['timer'] = GLib.timeout_add_seconds(180, timed_out)
        self.pending.append(pending)
        try:
            getattr(self.api, method)(*args, options, timeout=10)
        except Exception:
            cleanup()
            raise

    def start(self):
        self.request('CreateSession', (), self.created,
                     {'session_handle_token': 'tb' + uuid.uuid4().hex})

    def created(self, results):
        self.session = str(results['session_handle'])
        record_status(error='Waiting for desktop shortcut approval…')
        for signal, callback in (('Activated', self.activated), ('Deactivated', self.deactivated),
                                 ('ShortcutsChanged', self.changed)):
            self.session_matches.append(self.bus.add_signal_receiver(callback, signal_name=signal,
                dbus_interface='org.freedesktop.portal.GlobalShortcuts',
                bus_name='org.freedesktop.portal.Desktop'))
        shortcuts = self.dbus.Array([(key, self.dbus.Dictionary(
            {'description': row[0], 'preferred_trigger': TRIGGERS[key]}, signature='sv'))
            for key, row in BUTTONS.items()], signature='(sa{sv})')
        self.request('BindShortcuts', (self.dbus.ObjectPath(self.session), shortcuts, ''), self.bound)

    def bound(self, results):
        self.shortcuts = {}
        self.changed(self.session, results.get('shortcuts', []))

    def changed(self, session, shortcuts):
        if str(session) != self.session:
            return
        actual = getattr(self, 'shortcuts', {}).copy()
        actual.update({str(key): str(props.get('trigger_description', 'Unknown trigger')) for key, props in shortcuts})
        self.shortcuts = actual
        missing = sorted(set(BUTTONS) - set(actual))
        record_status(shortcuts=actual, error=('Unbound buttons: ' + ', '.join(missing) +
            '. Resolve conflicts in desktop shortcuts/portal settings.') if missing else '', last_button='')

    def activated(self, session, key, timestamp, options):
        key = str(key)
        if str(session) != self.session or key not in BUTTONS or key in self.active:
            return
        self.active.add(key)
        try:
            record_status(last_button=BUTTONS[key][0], error='')
            execute(load_settings()[key])
        except Exception as exc:
            record_status(error=str(exc))
            print(f'Toughbook Buttons: {exc}', file=sys.stderr, flush=True)

    def deactivated(self, session, key, timestamp, options):
        if str(session) == self.session:
            self.active.discard(str(key))

    def configure(self):
        if not self.session:
            raise ToolError('The shortcut portal session is not ready. Start the helper first.')
        try:
            self.api.ConfigureShortcuts(self.dbus.ObjectPath(self.session), '',
                self.dbus.Dictionary({}, signature='sv'), timeout=10)
        except Exception as exc:
            raise ToolError(f'Cannot open portal shortcut configuration: {exc}. Use desktop shortcut settings or update the portal backend.') from exc

    def close(self):
        self.clear_requests()
        self.clear_session_signals()
        if self.session:
            self.dbus.Interface(self.bus.get_object('org.freedesktop.portal.Desktop', self.session),
                                'org.freedesktop.portal.Session').Close(timeout=5)


def daemon():
    from gi.repository import GLib
    from .button_desktop import backend_name
    backend_name()
    lock = (state_dir() / 'buttons.lock').open('w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise ToolError('Toughbook Buttons helper is already running.')
    record_status(pid=os.getpid(), shortcuts={}, error='Connecting to shortcut portal…')
    portal = None
    final_message = 'Helper stopped'
    try:
        portal = Portal()
        from dbus import service
        class Control(service.Object):
            @service.method(CONTROL_IFACE, in_signature='', out_signature='')
            def Configure(self):
                portal.configure()
        control_name = service.BusName(CONTROL_IFACE, bus=portal.bus, do_not_queue=True)
        control = Control(control_name, CONTROL_PATH)
        loop = GLib.MainLoop()
        import signal
        def stop(*args):
            loop.quit()
        for sig in (signal.SIGTERM, signal.SIGINT):
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, stop)
        portal.start()
        loop.run()
    except Exception as exc:
        final_message = f'Helper failed: {exc}'
        raise
    finally:
        try:
            if portal:
                portal.close()
        finally:
            record_status(pid=None, shortcuts={}, error=final_message)
            lock.close()


def monitor():
    import struct
    paths = devices()
    if len(paths) != 1:
        raise ToolError(f'Expected one dedicated panasonic-hbtn device, found {len(paths)}. Install/load the driver first.')
    try:
        device = open(paths[0], 'rb', buffering=0)
    except PermissionError as exc:
        raise ToolError('Dedicated device access denied. Install the supplied narrowly matched uaccess rule; log in again.') from exc
    print(f'Identifying buttons on {paths[0]}; no device grab. Ctrl+C to stop.', flush=True)
    keys = {183 + i: row[0] for i, row in enumerate(BUTTONS.values())}
    # Linux input_event uses native timeval longs, followed by type/code/value.
    event_format = struct.Struct('llHHi')
    with device:
        while True:
            event = device.read(event_format.size)
            if len(event) != event_format.size:
                raise ToolError('Tablet input device disconnected; reload the driver and restart identification.')
            _, _, kind, code, value = event_format.unpack(event)
            if kind == 4 and code == 4:  # EV_MSC / MSC_SCAN
                print(f'Scan code 0x{value:02x}', flush=True)
            elif kind == 1 and value in (0, 1):  # EV_KEY, no repeats
                print(keys.get(code, f'Unknown key {code}'), 'pressed' if value else 'released', flush=True)


def integration_paths():
    data = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share')
    return data / 'toughbook-buttons', data / f'applications/{APP_ID}.desktop', config_dir() / f'autostart/{APP_ID}.desktop'


def exec_quote(path, systemd=False):
    value = str(path)
    if any(char in value for char in ('\n', '\r', '\0')):
        raise ToolError('Installation paths must not contain control characters.')
    value = value.replace('\\', '\\\\').replace('"', '\\"')
    if systemd:
        value = value.replace('$', '$$')
    else:
        value = value.replace('`', '\\`').replace('$', '\\$')
        # Desktop Entry string escaping precedes Exec argument parsing.
        value = value.replace('\\', '\\\\')
    return '"' + value.replace('%', '%%') + '"'


def integration(install):
    target, menu, autostart = integration_paths()
    service = config_dir() / 'systemd/user/toughbook-buttons.service'
    if not install:
        stopped = subprocess.run(['systemctl', '--user', 'stop', 'toughbook-buttons.service'], capture_output=True, text=True)
        if stopped.returncode and service.exists():
            raise ToolError('Cannot stop the session helper: ' + stopped.stderr.strip() + '. Run uninstall from your desktop terminal; installed files have been retained.')
        for path in (menu, autostart, service):
            path.unlink(missing_ok=True)
        if target.exists():
            shutil.rmtree(target)
        subprocess.run(['systemctl', '--user', 'daemon-reload'], capture_output=True)
        print('Removed app and session integration. Settings retained at', settings_path())
        return
    root = Path(__file__).resolve().parents[1]
    target.mkdir(parents=True, exist_ok=True)
    # Stage before replacement: rerunning the installed copy is supported.
    import tempfile
    with tempfile.TemporaryDirectory() as temporary:
        stage = Path(temporary)
        shutil.copytree(root / 'toughbook', stage / 'toughbook', ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copy2(root / 'toughbook-buttons.py', stage / 'toughbook-buttons.py')
        shutil.copytree(root / 'data', stage / 'data')
        shutil.copytree(stage, target, dirs_exist_ok=True)
    script = target / 'toughbook-buttons.py'
    command = '/usr/bin/python3 ' + exec_quote(script)
    service_command = '/usr/bin/python3 ' + exec_quote(script, systemd=True)
    menu.parent.mkdir(parents=True, exist_ok=True)
    menu.write_text((target/'data/org.toughbook.Buttons.desktop.in').read_text().replace('@PYTHON_EXEC@', command))
    autostart.parent.mkdir(parents=True, exist_ok=True)
    autostart.write_text((target/'data/org.toughbook.Buttons-autostart.desktop').read_text())
    service.parent.mkdir(parents=True, exist_ok=True)
    service.write_text((target/'data/toughbook-buttons.service.in').read_text().replace('@SERVICE_EXEC@', service_command))
    subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
    subprocess.run(['systemctl', '--user', 'restart', 'toughbook-buttons.service'], check=True)
    print('Installed Toughbook Buttons in the application menu and login autostart.')


def status():
    path = state_dir() / 'buttons-session.json'
    return {'driver_devices': devices(), 'portal': portal_status(), 'preferred_shortcuts': TRIGGERS, 'assignments': load_settings(),
            'session': json.loads(path.read_text()) if path.exists() else {'error': 'Helper has not started'}}


def gui():
    import gi
    gi.require_version('Gtk', '4.0')
    from gi.repository import Gtk, GLib, Gio
    app = Gtk.Application(application_id=APP_ID)
    def activate(application):
        window = Gtk.ApplicationWindow(application=application, title='Toughbook Buttons', default_width=660)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=18,
                      margin_bottom=18, margin_start=18, margin_end=18)
        scroll = Gtk.ScrolledWindow()
        scroll.set_child(box)
        window.set_default_size(660, 760)
        window.set_child(scroll)
        box.append(Gtk.Label(label='CF-19 tablet edge:  [ Keyboard ]  [ ○ ]  [ ↻ ]  [ Key ]', wrap=True))
        box.append(Gtk.Label(label='Single press assignments · brightness controls stay with the existing driver', wrap=True))
        initial_error = ''
        try:
            current = load_settings()
        except (ToolError, ValueError, OSError) as exc:
            current = defaults()
            initial_error = f'Could not load settings: {exc}. Review defaults below and Save to replace the invalid file.'
        rows = {}
        apps = sorted([a for a in Gio.AppInfo.get_all() if a.should_show() and a.get_id()], key=lambda a: a.get_name().casefold())
        choices = [('builtin', a, a.title()) for a in BUILTINS] + [('command', '', 'Executable with arguments'), ('shell', '', 'Explicit shell command')] + [('application', a.get_id(), a.get_name()) for a in apps]
        installed_ids = {choice[1] for choice in choices if choice[0] == 'application'}
        for assignment in current.values():
            if assignment['type'] == 'application' and assignment['value'] not in installed_ids:
                choices.append(('application', assignment['value'], 'Missing application: ' + assignment['value']))
                installed_ids.add(assignment['value'])
        for key, row in BUTTONS.items():
            box.append(Gtk.Label(label=f'{row[0]} ({row[2]}) — Windows: {row[1]}', xalign=0))
            dropdown = Gtk.DropDown.new_from_strings([c[2] for c in choices])
            assigned = current[key]
            dropdown.set_selected(next((i for i,c in enumerate(choices) if c[:2] == (assigned['type'], assigned['value']) or c[0] == assigned['type'] and c[0] in ('command','shell')), 0))
            entry = Gtk.Entry(text=assigned['value'] if assigned['type'] in ('command','shell') else '', placeholder_text='Executable and arguments; quote arguments containing spaces')
            box.append(dropdown)
            box.append(entry)
            def selected(d, p, e=entry):
                e.set_sensitive(choices[d.get_selected()][0] in ('command','shell'))
            dropdown.connect('notify::selected', selected)
            selected(dropdown, None)
            rows[key] = dropdown, entry
        message = Gtk.Label(label=initial_error, wrap=True, selectable=True, xalign=0)
        live = Gtk.Label(wrap=True, selectable=True, xalign=0)
        def save(_):
            try:
                data = {}
                for key, (drop, entry) in rows.items():
                    kind, value, _ = choices[drop.get_selected()]
                    data[key] = {'type': kind, 'value': entry.get_text() if kind in ('command','shell') else value}
                save_json(settings_path(), validate(data))
                message.set_label('Saved. The helper reads assignments on each press.')
            except Exception as exc:
                message.set_label(str(exc))
        button = Gtk.Button(label='Save assignments')
        button.connect('clicked', save)
        box.append(button)
        def reset(_):
            for key, (drop, entry) in rows.items():
                drop.set_selected(next(i for i,c in enumerate(choices) if c[:2] == ('builtin', BUTTONS[key][3])))
                entry.set_text('')
            save(None)
        button = Gtk.Button(label='Reset assignments to defaults')
        button.connect('clicked', reset)
        box.append(button)
        def start(_):
            try:
                integration(True)
                message.set_label('Helper started. Approve the portal shortcuts dialog.')
            except Exception as exc:
                message.set_label(str(exc))
        button = Gtk.Button(label='Install / start login helper')
        button.connect('clicked', start)
        box.append(button)
        def configure(_):
            try:
                import dbus
                proxy = dbus.SessionBus().get_object(CONTROL_IFACE, CONTROL_PATH)
                dbus.Interface(proxy, CONTROL_IFACE).Configure(timeout=15)
                message.set_label('Use the desktop dialog to record each physical button; actual shortcuts appear below.')
            except Exception as exc:
                message.set_label(f'Cannot configure shortcuts: {exc}. Install/start the helper first.')
        button = Gtk.Button(label='Configure global shortcuts…')
        button.connect('clicked', configure)
        box.append(button)
        box.append(message)
        box.append(live)
        def refresh():
            try:
                info = status()
                session = info['session']
                bindings = session.get('shortcuts', {})
                lines = ['Driver: ' + ('Ready' if info['driver_devices'] else 'Not detected; see driver installation instructions'),
                         info['portal'], 'Session helper: ' + ('running' if session.get('pid') else 'stopped'),
                         'Shortcuts: ' + ', '.join(f'{row[0]}: {bindings.get(key, "unbound")}' for key,row in BUTTONS.items())]
                if session.get('last_button'):
                    lines.append('Last button: ' + session['last_button'])
                if session.get('error'):
                    lines.append('Status: ' + session['error'])
                live.set_label('\n'.join(lines))
            except Exception as exc:
                live.set_label(str(exc))
            return True
        refresh()
        timer = GLib.timeout_add_seconds(2, refresh)
        window.connect('close-request', lambda *_: (GLib.source_remove(timer), False)[1])
        window.present()
    app.connect('activate', activate)
    return app.run([])


def main(argv=None):
    parser = argparse.ArgumentParser(description='Configure Panasonic CF-19 tablet buttons on Wayland')
    group = parser.add_mutually_exclusive_group()
    for mode in ('status', 'monitor', 'daemon', 'install', 'uninstall'):
        group.add_argument('--' + mode, action='store_true')
    args = parser.parse_args(argv)
    try:
        desktop_user()
        if args.status:
            print(json.dumps(status(), indent=2))
        elif args.monitor:
            monitor()
        elif args.daemon:
            daemon()
        elif args.install or args.uninstall:
            integration(args.install)
        else:
            return gui()
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f'Toughbook Buttons: {exc}', file=sys.stderr)
        return 1
