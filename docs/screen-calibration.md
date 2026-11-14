# Finger-touch calibration: issue and solution

On the reference CF-19 Mk6, the Wacom driver already exposed separate finger and
pen devices. Finger taps registered but missed their targets. A per-device affine
correction restored accurate finger input; this does not establish a universal
sensor defect or justify copying another laptop's coefficients. Only the Wacom
`056a:0093` finger interface `01` is selected. Pen devices are left unchanged.

## Measurement

The fullscreen window presents nine targets at 12%, 50% and 88% of each screen
axis. It waits for stable fullscreen geometry before accepting samples. The Qt
page receives native touchscreen events; the standalone Tk CLI receives finger
pointer emulation (through XWayland in a Wayland session).

Use only the internal screen at the origin, at 100% scale in normal landscape.
Do not rotate/change layout during measurement or preview. The fit solves:

```text
x_corrected = a*x_measured + b*y_measured + c
y_corrected = d*x_measured + e*y_measured + f
```

It rejects nonfinite/singular/reversed samples and maximum fitting residual above
20 pixels. Residual measures fit consistency, not independent accuracy; check
edges and corners in preview or verify actual taps after login. The correction
is composed with the current transform so repeat calibration preserves existing
correction.

## Setup and use

Install [Linux dependencies](linux.md), then use the Touchscreen page or CLI:

```sh
python3 tools/setup-linux.py
python3 calibrate-screen.py --status
python3 calibrate-screen.py
```

Desktop names do not gate calibration. The active session selects KWin live
calibration, native X11 calibration, or a persistent libinput rule. The Qt page
supports all three paths. Native Qt display discovery is used for generic
sessions, and rejects unknown/synthetic connectors, multiple outputs, scaling
and unexpected geometry. On Debian installations with a private PySide6 venv,
the standalone tool can use that installed interpreter for display discovery.

## KWin live calibration

The existing hardware-tested path uses KScreen's current layout and KWin's live
per-device calibration/output properties. The affine transform occupies the
top-left 3×3 portion of KWin's serialized 4×4 matrix; translations are in the
third column. The implementation writes and reads back the matrix.

Accept after testing finger accuracy. Escape, close, resized geometry or an error
requests restoration of the previous matrix and output assignment. Accepted
settings are persisted by KWin. Backup identity resolves the current event node,
so restoration does not depend on an old `/dev/input/eventN` number.

## Native X11 calibration

On any native X11 desktop/window manager, the tool resolves the finger device by
matching XInput's `Device Node` to the discovered finger event. It changes only
that device's Coordinate Transformation Matrix, reads it back, and previews it.
It never uses XInput against XWayland. Pen/ordinary keyboard devices are excluded.

Accepting stores a per-user activation record at
`$XDG_CONFIG_HOME/toughbook-tools/x11-calibration.json` and an XDG autostart entry.
It uses the installed app copy when available. Cancellation/save failure restores
the previous live matrix and activation record. Restore also reinstates/removes
the previous activation record. For window managers without XDG autostart, run
`python3 calibrate-screen.py --activate` after X startup. Activation refuses a
changed display layout; return to the original normal layout first.

The Rotation button's X11 backend composes output orientation with the existing
finger transform and attempts to restore both if a change fails. Ubuntu GNOME X11
has physical rotation and calibration evidence. A full reboot/login restored the
saved matrix automatically; post-reboot finger error was at most 14.07 pixels
against a 20-pixel limit. An earlier unexplained live-matrix reset was corrected
by reapplying the intact saved calibration. Other desktops and suspend/resume
still need checks; see [validation results](VALIDATION.md).

## Common libinput Wayland calibration

Other libinput-based Wayland compositors, including GNOME, use the same narrow
udev rule. A running Mutter interface can supply display layout; other compositors
use native Qt. Measuring/saving a candidate does not change live input.

In the GUI, save the candidate, select it below, choose **Apply candidate**, approve
the administrator prompt, log out/in and use **Verify after login**. GUI
verification uses native Qt and does not require XWayland. The CLI prints
the equivalent commands:

```sh
python3 calibrate-screen.py --apply BACKUP
# Log out and back in, then:
python3 calibrate-screen.py --verify BACKUP
# Or use native Qt targets without XWayland:
python3 calibrate-screen.py --verify BACKUP --qt
```

The rule sets `LIBINPUT_CALIBRATION_MATRIX` in:

```text
/etc/udev/rules.d/99-toughbook-fedora-touchscreen.rules
```

The historical filename is retained for recovery compatibility. Matching includes
the vendor/product, touchscreen classification, finger USB interface, serial and
internal USB path. No broad input-device rule is generated. A prior rule is backed
up verbatim, and applying refuses if that rule changed since measurement.

Libinput reads this default when creating a device. Reloading udev alone does
not prove that the running compositor re-read it, so verification requires a new
login, expected udev matrix and another actual nine-point measurement. It reports
success only after those checks and acceptance. Generic login identity comes from
logind; ambiguous/unavailable sessions are refused. GNOME retains its existing
shell-session identity compatibility for older backups.

A compositor may override libinput defaults. Remove/restore any conflicting
per-compositor transform before using this path. Restore an old KWin-specific
matrix before switching to a common rule to avoid applying two corrections.
Physical validation on additional compositors remains pending.

## Recovery and troubleshooting

All paths retain a JSON backup in the tool's private state directory. Use the
GUI's **Restore selected backup** or:

```sh
python3 calibrate-screen.py --restore BACKUP
```

KWin/X11 restore the previous live matrix. Libinput restores the old rule or
removes the tool's rule, then requires logout/login. Preserve backups until
accuracy is confirmed. Run as the original desktop user; system-rule changes
request administrator authorization separately. The GUI uses graphical polkit
authorization; the terminal CLI uses sudo.

- **No sensor:** inspect `--status` and the exact finger USB interface; never
  substitute the pen or guess an event node.
- **Layout refused:** disable external displays, use 100% scale at the origin,
  and return to normal landscape. Generic discovery must run against the native
  display connection. Install Qt's native Wayland plugin where required.
- **Inaccurate preview:** cancel and retry with deliberate finger taps. A good
  fit residual alone does not prove touch accuracy.
- **Verification refused:** log out/in after applying, confirm the expected udev
  matrix and unchanged geometry, then retry. Restore if actual taps still miss.
- **Session interrupted:** keep the printed backup and explicitly restore it;
  abrupt process termination cannot guarantee live rollback.

See [desktop compatibility](desktops.md) and [validation status](VALIDATION.md).
Sources: [KWin device implementation](https://github.com/KDE/kwin/blob/master/src/backends/libinput/device.cpp),
[libinput udev defaults](https://wayland.freedesktop.org/libinput/doc/latest/device-configuration-via-udev.html),
[XInput](https://www.x.org/releases/current/doc/man/man1/xinput.1.xhtml).


## System-wide libinput pilot

The reference Ubuntu X11 device passed a local trial that stores sensor correction
in a udev libinput default and switches only the finger interface to the Xorg
libinput driver. Login, lock, suspend and rotation checks passed without the local
guard; physical finger error was at most 9.63 pixels. Pen/eraser behavior was
confirmed unchanged. See [validation results](VALIDATION.md).

The app now offers an integrated workflow below. The standalone pilot results
validate the configuration approach; physical acceptance of the new app workflow
on Ubuntu and Fedora remains pending.

## System-wide login and desktop calibration

Use **Calibrate for login and desktop** on the Finger touch page. It measures a
candidate without changing live input. Save it, select the new backup, choose
**Apply candidate**, and authorize installation. Reboot, select the same backup,
and use **Verify after login**. Also check touch at the actual login screen.
Verification requires a new boot, the expected rule and live driver calibration,
and physical targets within the existing 20-pixel maximum-error limit.

The equivalent source commands are:

```sh
python3 calibrate-screen.py --system-wide
python3 calibrate-screen.py --apply /path/to/screen-backup.json
# Reboot, then:
python3 calibrate-screen.py --verify /path/to/screen-backup.json
python3 calibrate-screen.py --restore /path/to/screen-backup.json
# Reboot after restore too.
```

Portable commands use `./toughbook-tools --tool screen` in place of
`python3 calibrate-screen.py`. The portable runtime still requires host udev,
polkit/sudo, and the host Xorg libinput driver; it does not supply an Xorg server
or driver. The privileged helper uses the application's own interpreter, so this
workflow does not add a system-Python requirement to portable installations.

Ubuntu setup includes `xserver-xorg-input-libinput`; Fedora setup includes
`xorg-x11-drv-libinput`. Rerun setup when upgrading an existing installation.
The same workflow works with native X11 and Wayland sessions; selecting libinput
in Xorg only changes X11 finger input. Pen/eraser retain their existing drivers.
Native Wayland and Fedora hardware acceptance remain separate checks.

Installation retains the existing udev-rule filename for compatibility and
manages `/etc/X11/xorg.conf.d/99-toughbook-finger-calibration.conf`. It narrowly
matches the finger interface, applies sensor correction through libinput, and
keeps the X11 coordinate transform available for display mapping and rotation.
KDE's saved compositor calibration is updated to the measured matrix rather than
stacking a second correction. Fedora system files are relabeled with restorecon
when available.

Backups record exact prior system files, the user's old calibration activation
and startup files, and any recognized local touch-guard state. The known legacy
finger `xinput.desktop` entry is retired; unrelated entries are not deleted.
Configuration changes since measurement or installation cause a refusal instead
of an overwrite. System-file writes are staged and rolled back on partial failure.
An interrupted install retains a recovery backup; restore it before retrying.

Restore reinstates the saved files and KDE calibration and requires a reboot.
The local guard’s previous enablement is restored for the next graphical
session rather than starting it over a still-active libinput correction. If it
was running manually but not enabled, restart it manually only after reboot. Removing
the application alone does not remove system calibration; restore its backup
first if you want to undo the calibration.

When driver calibration is active, legacy X11 measurement and restore are refused,
and legacy `--activate` skips applying a second matrix. After a new system
calibration, use this system workflow to recalibrate. It composes measured
correction with the effective driver/display calibration exactly once.
