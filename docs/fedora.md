# Fedora KDE retest of the current source

This is an acceptance checklist for a traditional, writable Fedora installation
on the reference CF-19 Mk6. Earlier Fedora 44 KDE Wayland testing established
the original hardware workarounds, but it predates the current system-wide
calibration workflow, button helper, GUI safety changes and pen rollback. Record
the actual Fedora, Plasma, kernel and package versions used; this document does
not claim the current build passed on Fedora. Silverblue/Kinoite need a separate
installation path.

## Prepare and capture a baseline

Use a backup or test installation and a normal desktop account with sudo. Keep a
physical keyboard available for login and recovery. From a fresh clone of the
current `main` commit, record `git rev-parse HEAD`, `cat /etc/fedora-release`,
`uname -r`, `echo "$XDG_SESSION_TYPE $XDG_CURRENT_DESKTOP"`, `mokutil --sb-state`
(when available), `pactl info`, and `python3 toughbook-tools.py --status`.
Record `lsusb -d 056a:0093`, the finger and pen names from `libinput list-devices`,
and the codec and `MAT001F` identity. Note any existing udev calibration rule,
Xorg override, audio repair backup, driver module, or button settings before
changing them. Do not overwrite an unrelated existing configuration.

Run the read-only package preview first:

```sh
sudo dnf install git python3
git clone https://github.com/the1glorfindel/toughbook-linux-tools.git
cd toughbook-linux-tools
python3 tools/setup-linux.py --dry-run --desktop kde
```

On a clean test installation, run `python3 tools/setup-linux.py --desktop kde`,
then `python3 toughbook-tools.py --status` and open Toughbook Tools. Setup installs
app dependencies and a per-user launcher; it does not apply fixes or install the
optional kernel driver. A KDE polkit agent is needed for later system calibration
and driver actions. Run the suite with `python3 -m unittest discover -s tests`.
Run `python3 tools/check-display.py --expect wayland` in the real Wayland desktop
for a GUI smoke check; this uses synthetic touches and makes no hardware changes.

## Physical acceptance, one change at a time

1. **Finger calibration:** On the internal display at normal orientation and
   100% scale, measure a system candidate, apply it with administrator
   authorization, inspect the finger-only udev rule, reboot, and verify the
   nine targets. Record maximum pixel error and whether the boot login, lock
   and unlock screens are accurate. Check pen tracking separately. Restore the
   saved calibration from the app, reboot, and verify the previous mapping.
   Include one canceled authorization or invalid-candidate attempt; confirm
   prior configuration remains intact. The legacy session-only path is under
   Advanced options and is not a substitute for boot login calibration.
2. **Audio:** Record PipeWire and WirePlumber versions. Confirm both speaker
   samples before/after repair, headphone behavior, and output after a new
   login and suspend. Restore from the app's saved backup and verify the
   prior mixer/profile files. Follow [audio recovery](audio-fix.md) if playback
   or rollback fails.
3. **Front buttons:** If absent, install exact running-kernel development files
   and the optional driver using [driver installation](driver-installation.md).
   With Secure Boot, enroll the host's configured DKMS signing key before
   loading. Confirm four named press/release pairs in Identify mode without
   assigned actions firing. Then test Keyboard, Circle, Rotation through four
   orientations, and Key lock. Verify actions are blocked while locked and
   restored afterward. Repeat after login and suspend; record helper health.
4. **Pen:** Check tracking and the native side-button behavior independently.
   The app currently offers Desktop default and original-mapping restore on
   KDE Wayland. Right/middle/left remap choices are disabled after failed
   Plasma 5.27 tests. If restoring a prior mapping, save work and log out/in;
   verify the result at the pen position. Never reload KWin plugins for this.

For each step, record observed result, failure text, session type, and whether
the check used the installed source app or a separate tool. Mark skipped cases
as skipped, not passed. If an app action could disturb the desktop or reboot,
perform it only with the tester present and save work first. Do not distribute
the old 0.2.0 portable artifact as evidence for this source revision.

## Acceptance and recovery

Fedora current-source acceptance requires successful setup, native GUI smoke,
the app-managed calibration apply/reboot/verify/restore cycle, audio repair and
restore, four-button input/actions, login and suspend persistence, and no KDE
session loss. Pen remapping remains outside this acceptance claim. Record exact
failures in [validation status](VALIDATION.md) and leave the feature unaccepted
until retested. Existing calibration and audio backups should remain available
through the app; `python3 toughbook-tools.py --uninstall` removes app integration
while retaining user settings and recovery backups. Driver removal is separate.
