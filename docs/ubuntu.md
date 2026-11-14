# Ubuntu bring-up

For shared Debian/Ubuntu, Fedora and Arch setup, start with
[Linux installation and compatibility](linux.md).

Ubuntu has live validation on the same CF-19 Mk6 hardware as the Fedora
implementation. Specific Ubuntu 24.04 GNOME X11 hardware checks are recorded in
[validation status](VALIDATION.md); clean setup, DKMS and other Ubuntu sessions
still need acceptance testing. Use a local Wayland or X11 graphical session. See [desktop compatibility](desktops.md)
for common calibration and dedicated-device button delivery. Other CF-19 revisions
remain outside the tested hardware scope.

## Install

From a fresh Ubuntu desktop, as the logged-in user:

```sh
sudo apt-get update
sudo apt-get install -y git python3
git clone https://github.com/the1glorfindel/toughbook-linux-tools.git
cd toughbook-linux-tools
python3 tools/setup-linux.py
python3 toughbook-tools.py --status
```

Open **Toughbook Tools** from the application menu after setup finishes.

The script uses APT for Python, D-Bus, Tk, XWayland, PipeWire, WirePlumber,
ALSA and portal packages. Add `--driver-prerequisites` for DKMS, compiler,
Secure Boot tools and matching kernel-header packages.
It installs PySide6 from APT when available. Ubuntu 24.04 lacks that package,
so the script creates a persistent virtual environment with access to Ubuntu's
system `dbus` and `gi` Python modules and installs PySide6 there. The application
menu entry uses the selected interpreter.

Ordinary setup does not require headers. If matching headers are unavailable,
omit `--driver-prerequisites`. The optional button driver cannot be built until the corresponding `linux-headers-$(uname -r)` package or kernel
header tree is available. Reboot into a packaged Ubuntu kernel if needed.

Run `python3 toughbook-tools.py --status` for a read-only hardware check, then
launch **Toughbook Tools** from the application menu. The Qt calibration page
selects a live KWin/X11 path or a libinput candidate workflow. Touchscreen and
button actions need a local graphical session. The audio repair also
requires that the card be managed by PipeWire and WirePlumber; it will inspect
the installed profile format before changing audio settings.

## Distribution differences

- The optional DKMS installer checks `/lib/modules/$(uname -r)/build`, which
  works with Ubuntu's `linux-headers-*` and Fedora's `kernel-devel-*` layouts.
- The Buttons page uses APT on Debian/Ubuntu, DNF on Fedora and Pacman on Arch
  for driver build prerequisites. It never replaces another driver bound to `MAT001F`.
- Ubuntu 24.04 ships WirePlumber 0.4, whose ALSA rules are Lua fragments under
  `~/.config/wireplumber/main.lua.d/`. Newer WirePlumber 0.5 uses `.conf`
  fragments under `~/.config/wireplumber/wireplumber.conf.d/`. The audio tool
  selects the format from `wireplumber --version` and retains exact backups.
- KDE needs `kscreen-doctor`; the setup script installs the package that
  supplies it when run in a KDE session. GNOME display discovery uses D-Bus.

## First checks after switching

1. Confirm the CF-19 revision, Wacom finger interface, Realtek codec, and
   `MAT001F` device with `python3 toughbook-tools.py --status`.
2. Check the session type (`echo "$XDG_SESSION_TYPE"`) and ensure only the
   internal display is active before calibrating finger touch.
3. Test speaker playback and its restoration workflow before saving a repair.
4. Check whether an Ubuntu kernel driver already owns `MAT001F`. Install the
   optional driver only if the Buttons page reports no competing binding.
5. If Secure Boot is enabled, follow [MOK enrollment](driver-installation.md)
   before loading the DKMS module.

Keep the Fedora installation and its saved backups available until Ubuntu's
display, audio, button, suspend, and login behavior has been checked in person.


## Current reference-device results

Ubuntu 24.04.4 GNOME 46 X11 on CF-192NYZX1M passed a full reboot/login check:
saved finger calibration applied automatically and the source button helper
started without error. The user confirmed both speaker samples and all four
physical button press/release pairs after reboot. Finger verification measured
14.07 pixels maximum error, below the 20-pixel limit.

A prior live-matrix reset required reapplying the intact saved calibration; its
cause remains unknown. Suspend/resume and native GNOME Wayland remain untested
in this retest. Portable packaging/X11 smoke checks passed separately; the portable
helper has not replaced the source installation. See [validation status](VALIDATION.md).


The app's **Calibrate for login and desktop** workflow now installs the narrow
libinput rule and finger-only Xorg driver selection tested in the device pilot.
It includes reboot verification, backup/restore, and migration away from the old
per-user activation. Follow [system-wide calibration](screen-calibration.md#system-wide-login-and-desktop-calibration);
the old manual pilot install script is not needed for new app-managed candidates.
