# Finger-touch calibration: issue and solution

## What was observed

On the tested CF-19 Mk6, Linux already loaded the Wacom driver and exposed separate
`Wacom ISDv4 93 Finger` and pen devices. Finger taps registered, but landed away
from the intended point. The default calibration was the identity transform;
measured taps showed scale and offset errors across the built-in 1024×768 panel.
A per-device affine correction restored accurate finger input.

This establishes a coordinate-mapping mismatch on the tested machine. It does
not establish a defective sensor, a missing kernel driver, or a Fedora-wide bug.
The active pen has its own coordinate stream and is deliberately left unchanged.
Never copy another laptop's calibration coefficients as a universal fix.

## How measurement works

The fullscreen window places nine targets on a 3×3 grid, at 12%, 50%, and 88% of
each dimension. Finger taps are received through XWayland's pointer emulation
using Tk. The window must first match the active internal display's dimensions
and remain stable for several checks. Sampling starts only then; resizing during
measurement clears the samples. A resize during the KDE preview cancels it.

The implementation fits a least-squares affine correction in normalized screen
coordinates:

```text
x_corrected = a*x_measured + b*y_measured + c
y_corrected = d*x_measured + e*y_measured + f
```

This corrects translation, scale, and small cross-axis skew. It rejects nonfinite,
singular, reversed-axis, or inconsistent samples (maximum fitting residual above
20 pixels). The residual measures consistency of the fit, not independent proof
of touch accuracy. A user preview or a fresh verification pass is still required.
The correction is composed with the current calibration, so repeat calibration
does not throw away a preexisting transform.

The original prototype had two implementation errors: it measured the window
before fullscreen had settled, and placed translations in the wrong matrix
column. These were tool bugs, not causes of the laptop's original touch offset.
The released implementation explicitly checks geometry and matrix format.

## KDE Wayland backend

Display discovery uses `kscreen-doctor -j`. Device identity comes from udev;
KWin's `org.kde.KWin.InputDevice` D-Bus properties provide the live matrix and
output mapping. The six affine coefficients occupy the top-left 3×3 portion of
KWin's serialized 4×4 matrix:

```text
a b c 0
d e f 0
0 0 1 0
0 0 0 1
```

In particular, translation belongs in the **third column**, not the fourth.
The tool sets the detected internal output, writes the matrix, and reads it back.
KWin persists accepted settings in the user's input configuration. Enter accepts;
Escape, closing the window, or an application error restores the previous matrix
and output mapping. Backups record stable hardware identity so restore resolves
the current event device instead of relying on an old `/dev/input/eventN` number.

## GNOME Wayland backend — experimental

GNOME's touchscreen GSettings schema offers output mapping, not an equivalent
public calibration-matrix setting. This backend therefore uses libinput's
`LIBINPUT_CALIBRATION_MATRIX` udev property. It stores six normalized coefficients,
composed with the existing property, in:

```text
/etc/udev/rules.d/99-toughbook-fedora-touchscreen.rules
```

The rule matches vendor/product `056a:0093`, finger USB interface `01`, touchscreen
classification, serial, and the internal USB path. It does not match the pen
interface or all input devices. Only the explicit `--apply BACKUP` operation uses
sudo to install the generated file, reload rules, and refresh the selected event.
The GUI itself never runs as root. An existing tool rule is backed up before
replacement; if it changes after measurement, installation stops.

Libinput reads this static property when adding the device to a context. Updating
the udev database alone does not guarantee that a running GNOME session rereads
it, hence the required logout/login. Verification checks the new shell-session
identity, expected udev matrix, and another nine-point set of actual taps. It
reports failure rather than calling an unverified candidate successful. Restore
uses the prior rule contents, or removes the tool's rule if none existed, and
requires another logout/login.

This path is implemented and covered by simulations, but has **not** been tested
on physical CF-19 hardware running GNOME. GNOME support remains experimental in this release.
For v1, keep one internal display active, at 100% scale in normal landscape.
Rotation, fractional scaling, and multiple active monitors need separate validation.
Do not assume a GNOME system rule replaces a previously saved KWin user matrix
when switching desktop sessions; calibrate/restore using the appropriate backend.

## Sources

- [KWin device properties and matrix implementation](https://github.com/KDE/kwin/blob/master/src/backends/libinput/device.cpp)
- [libinput static configuration through udev](https://wayland.freedesktop.org/libinput/doc/latest/device-configuration-via-udev.html)
- [GNOME peripheral schemas](https://github.com/GNOME/gsettings-desktop-schemas/blob/master/schemas/org.gnome.desktop.peripherals.gschema.xml.in)
