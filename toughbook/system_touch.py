"""System-wide libinput sensor calibration with recoverable configuration changes. MIT."""
import base64
import json
from pathlib import Path
import tempfile
import os
from . import runtime
from .affine import IDENTITY, compose, from_kwin, validate
from .common import ToolError, config_dir, load_json, run, save_json, backup_path

XORG = Path('/etc/X11/xorg.conf.d/99-toughbook-finger-calibration.conf')
XORG_CONTENT = '''# Managed by Toughbook Tools. Finger interface only; pen remains unchanged.
Section "InputClass"
    Identifier "Toughbook libinput finger calibration"
    MatchUSBID "056a:0093"
    MatchProduct "Wacom ISDv4 93 Finger"
    MatchIsTouchscreen "on"
    MatchDevicePath "/dev/input/event*"
    Driver "libinput"
    Option "TransformationMatrix" "1 0 0 0 1 0 0 0 1"
EndSection
'''


def same(a, b):
    return len(a) == len(b) and max(abs(x-y) for x,y in zip(a,b)) < 1e-4


def driver_matrix(device):
    """Read the effective X11 driver correction, independently of display mapping."""
    from .xinput import XInput
    touch = XInput(device)
    props = run('xinput', 'list-props', touch.id).stdout
    for line in props.splitlines():
        if line.strip().startswith('libinput Calibration Matrix ('):
            values = validate(line.split(':', 1)[1].split(','), 9)
            if values[6:] != [0.,0.,1.]:
                raise ToolError('Unsupported driver calibration perspective.')
            return values[:6]
    return list(IDENTITY)


def read_files(paths):
    return {str(p): base64.b64encode(p.read_bytes()).decode() if p.exists() else None for p in paths}


def user_paths():
    return [config_dir()/'autostart/xinput.desktop', config_dir()/'autostart/org.toughbook.Touchscreen.desktop',
            config_dir()/'toughbook-tools/x11-calibration.json']


def system_paths():
    from .screen import RULE
    return [RULE, XORG]


def baseline(backend, device):
    from .screen import KWin
    from .xinput import XInput
    if backend == 'x11':
        return compose(XInput(device).get()['matrix'], driver_matrix(device))
    if backend == 'kde':
        return from_kwin(KWin(device).get()['matrix'])
    return validate(device['properties'].get('LIBINPUT_CALIBRATION_MATRIX', '1 0 0 0 1 0').split())


def candidate(device, matrix, size):
    from .screen import make_rule
    make_rule(device['identity'], matrix)  # Validate before saving or requesting privilege.
    result = {'kind':'screen', 'backend':'system', 'identity':device['identity'],
            'matrix':validate(matrix), 'size':list(size), 'status':'candidate',
            'previous':{'system_files':read_files(system_paths()),
                        'user_files':read_files(user_paths())}}
    from .screen import backend_name, KWin
    if backend_name() == 'kde':
        result['previous']['kwin'] = KWin(device).get()
    return result


# Execute standard-library operations using the app interpreter, including in
# portable builds. The elevated helper writes only the two fixed system targets.
HELPER = r'''
import base64,json,os,sys,tempfile
from pathlib import Path
request=json.loads(Path(sys.argv[1]).read_text())
allowed={'/etc/udev/rules.d/99-toughbook-fedora-touchscreen.rules','/etc/X11/xorg.conf.d/99-toughbook-finger-calibration.conf'}
if set(request['expected'])!=allowed or set(request['desired'])!=allowed:raise SystemExit('Invalid target paths')
def read(p):return base64.b64encode(p.read_bytes()).decode() if p.exists() else None
for name,value in request['expected'].items():
 p=Path(name)
 if p.is_symlink() or read(p)!=value:raise SystemExit('Configuration changed: '+name)
def write(name,value):
 p=Path(name)
 if value is None:p.unlink(missing_ok=True);return
 p.parent.mkdir(parents=True,exist_ok=True)
 fd,tmp=tempfile.mkstemp(prefix='.toughbook-',dir=p.parent)
 try:
  with os.fdopen(fd,'wb') as f:f.write(base64.b64decode(value,validate=True))
  os.chmod(tmp,0o644);os.replace(tmp,p)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)
try:
 for name,value in request['desired'].items():write(name,value)
 import subprocess
 for command in ('/sbin/restorecon','/usr/sbin/restorecon'):
  if Path(command).exists():
   subprocess.run([command,'-F',*[name for name in allowed if Path(name).exists()]],check=True)
   break
except BaseException:
 for name,value in request['expected'].items():write(name,value)
 raise
'''


def change_files(expected, desired, privilege):
    if privilege not in ('sudo','pkexec'):
        raise ToolError('Unsupported authorization method.')
    with tempfile.TemporaryDirectory(prefix='toughbook-system-touch-') as folder:
        request = Path(folder)/'request.json'
        request.write_text(json.dumps({'expected':expected,'desired':desired}))
        run(privilege, *runtime.command('calibrate-screen.py', '--system-touch-helper', str(request)), timeout=120)


def restore_user(files):
    if set(files) != {str(p) for p in user_paths()}:
        raise ToolError('Backup belongs to a different user configuration directory.')
    for name, value in files.items():
        p = Path(name)
        if value is None:
            p.unlink(missing_ok=True)
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(base64.b64decode(value, validate=True))


def apply(path, privilege):
    from . import screen
    data = load_json(path, 'screen')
    if data['backend'] != 'system' or data['status'] != 'candidate':
        raise ToolError('Select a saved system-wide calibration candidate.')
    device = screen.find_saved_device(data)
    driver_paths = ('/usr/lib/xorg/modules/input/libinput_drv.so',
                    '/usr/lib64/xorg/modules/input/libinput_drv.so')
    if not any(Path(p).is_file() for p in driver_paths):
        raise ToolError('Install the host Xorg libinput driver using tools/setup-linux.py before applying system calibration.')
    backend = screen.backend_name()
    if list(screen.layout(backend)[1:]) != data['size']:
        raise ToolError('Restore the measured display layout before installing.')
    previous = data['previous']
    if read_files(system_paths()) != previous['system_files'] or read_files(user_paths()) != previous['user_files']:
        raise ToolError('Calibration configuration changed since measurement; create a new candidate.')
    rule = screen.make_rule(device['identity'], data['matrix']).rstrip()+', ENV{ID_INPUT_TABLET}=""\n'
    desired = {str(screen.RULE):base64.b64encode(rule.encode()).decode(),
               str(XORG):base64.b64encode(XORG_CONTENT.encode()).decode()}
    guard = config_dir()/'systemd/user/toughbook-touch-guard.service'
    if guard.exists():
        if 'touch-calibration-guard.py' not in guard.read_text():
            raise ToolError('Unknown touch guard service; disable it before installation.')
        data['previous']['guard'] = {action: run('systemctl', '--user', action, 'toughbook-touch-guard.service', check=False).returncode == 0 for action in ('is-enabled', 'is-active')}
    if backend == 'kde':
        if 'kwin' not in previous or screen.KWin(device).get() != previous['kwin']:
            raise ToolError('KDE calibration changed since measurement; create a new candidate.')
    elif 'kwin' in previous:
        raise ToolError('Install this KDE candidate from the KDE session where it was measured.')
    legacy = config_dir()/'autostart/xinput.desktop'
    if legacy.exists() and not all(text in legacy.read_text() for text in ('Wacom ISDv4 93 Finger', 'Coordinate Transformation Matrix')):
        raise ToolError('An unrelated xinput startup entry exists; move it before installing system calibration.')
    data.update(status='installing', installed_files=desired,
                boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    save_json(path, data)
    changed = False
    try:
        change_files(previous['system_files'], desired, privilege); changed = True
        run(privilege, 'udevadm', 'control', '--reload-rules', timeout=120)
        if 'guard' in previous:
            run('systemctl', '--user', 'disable', '--now', 'toughbook-touch-guard.service')
        if backend == 'kde':
            from .affine import to_kwin
            screen.KWin(device).set(to_kwin(data['matrix']), previous['kwin']['output'])
        for p in user_paths():
            p.unlink(missing_ok=True)
        data['status'] = 'pending-reboot'; save_json(path, data)
    except BaseException:
        # Do not overwrite an administrator edit made during a failed operation.
        if changed:
            change_files(desired, previous['system_files'], privilege)
            run(privilege, 'udevadm', 'control', '--reload-rules', timeout=120)
            restore_user(previous['user_files'])
            restore_session(previous, device)
        raise
    print('System calibration installed. Reboot before verification. Backup:', path)


def restore(path, privilege):
    data = load_json(path, 'screen')
    if data.get('backend') != 'system' or data.get('status') not in ('installing','pending-reboot','accepted'):
        raise ToolError('Select an installed system calibration backup.')
    current = read_files(system_paths())
    if current not in (data['installed_files'], data['previous']['system_files']):
        raise ToolError('System configuration changed since installation; refusing to overwrite it.')
    change_files(current, data['previous']['system_files'], privilege)
    run(privilege, 'udevadm', 'control', '--reload-rules', timeout=120)
    restore_user(data['previous']['user_files'])
    from .screen import find_saved_device
    restore_session(data['previous'], find_saved_device(data) if 'kwin' in data['previous'] else None)
    data['status'] = 'restored'; save_json(path, data)
    print('Previous calibration configuration restored. Reboot to activate it.')


def measure(device, backend, size):
    """Measure without changing either the driver or display transform."""
    from PySide6.QtWidgets import QApplication
    from .screen_gui import _Targets
    from .affine import fit
    app = QApplication.instance() or QApplication([])
    dialog = _Targets(size); result = {'path':None, 'error':None}
    old = baseline(backend, device)
    initial = candidate(device, old, size)
    def measured(samples):
        try:
            correction, error = fit(samples, *size)
            data = dict(initial)
            data['matrix'] = compose(correction, old)
            data['fit_error_pixels'] = error
            result['data'] = data
            dialog.show_preview(); dialog.keep.setText('Save system candidate')
            dialog.message = 'Measurement complete. Save, install the candidate, then reboot to verify.'
            dialog.update()
        except Exception as exc:
            result['error'] = exc; dialog.finish(); app.quit()
    def save():
        path = backup_path('screen'); save_json(path, result['data'])
        result['path'] = path; dialog.finish(); app.quit()
    dialog.measured.connect(measured); dialog.accepted_result.connect(save)
    dialog.cancelled.connect(lambda: (dialog.finish(), app.quit()))
    import signal
    handlers = {sig: signal.signal(sig, lambda *_: (dialog.finish(), app.quit()))
                for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        app.exec()
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)
        dialog.finish()
    if result['error']:
        raise result['error']
    return result['path']


def verify(path, device, backend, size):
    from .screen import KWin
    from .screen_gui import verify_targets
    data = load_json(path, 'screen')
    if data.get('status') != 'pending-reboot':
        raise ToolError('Select an installed system candidate awaiting reboot.')
    if data['boot_id'] == Path('/proc/sys/kernel/random/boot_id').read_text().strip():
        raise ToolError('Reboot before verifying system calibration.')
    if list(size) != data['size'] or read_files(system_paths()) != data['installed_files']:
        raise ToolError('Display layout or installed calibration configuration changed.')
    actual = validate(device['properties'].get('LIBINPUT_CALIBRATION_MATRIX', '').split())
    if not same(actual, validate(data['matrix'])):
        raise ToolError('udev calibration does not match the installed candidate.')
    if backend == 'x11':
        from .xinput import XInput
        if not same(driver_matrix(device), actual) or not same(XInput(device).get()['matrix'], IDENTITY):
            raise ToolError('X11 driver calibration or display transform differs; refusing double calibration.')
    elif backend == 'kde':
        if not same(from_kwin(KWin(device).get()['matrix']), actual):
            raise ToolError('KDE has an overriding calibration. Restore or remove the override before verification.')
    if not verify_targets(size):
        return 2
    data['status'] = 'accepted'; save_json(path, data)
    print('System-wide finger calibration verified. Login-screen accuracy still requires a physical check.')
    return 0


def restore_session(previous, device):
    if 'kwin' in previous:
        from .screen import KWin
        KWin(device).restore(previous['kwin'])
    guard = previous.get('guard', {})
    # Starting the old guard before reboot could double-correct a live libinput device.
    for action, needed in [('enable', guard.get('is-enabled'))]:
        if needed:
            run('systemctl', '--user', action, 'toughbook-touch-guard.service')


def privileged_helper(request):
    if os.geteuid() != 0:
        raise ToolError('The system calibration helper requires administrator authorization.')
    import sys
    previous = sys.argv
    try:
        sys.argv = ['system-touch-helper', str(request)]
        exec(compile(HELPER, '<system-touch-helper>', 'exec'), {'__name__':'__main__'})
    finally:
        sys.argv = previous
