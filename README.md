# Toughbook Tools for Linux

**Toughbook Tools** is a Linux desktop app for three Panasonic CF-19 Mk6
issues: inaccurate finger touch, silent internal speakers, and missing tablet
buttons. It guides calibration and speaker repair, manages the four button
assignments, and shows recovery options and troubleshooting output. The optional
button driver is GPL-2.0-only; the application is MIT licensed.

| Feature | Tested hardware | Desktop support |
| --- | --- | --- |
| Finger touch | Wacom `056a:0093` finger interface | KWin live preview, generic libinput Wayland, native X11 |
| Internal speaker | Realtek ALC269VC | PipeWire/WirePlumber; Fedora KDE workflow tested |
| Tablet buttons | CF-19 Mk6 board `CF19-6`, ACPI `MAT001F` | Dedicated-device input across desktops; optional shortcut portal |

Other CF-19 revisions, the active Wacom pen, other touch controllers, and
other audio codecs are outside the tested scope. The detailed
[documentation index](docs/README.md) explains each issue and its recovery path.

## Current release and testing status

The current build is ready for preview testing; stable portable-release acceptance
is incomplete. On the reference CF-19, Ubuntu 24.04.4 GNOME 46 X11 checks confirm
internal-speaker playback, all four button inputs, and saved touch calibration
and helper startup after a full reboot. Post-reboot finger verification measured
14.07 pixels maximum error against a 20-pixel limit.

The portable 0.2.0 build passed clean-container runtime checks, native X11 GUI
checks, and isolated install/upgrade/uninstall checks. The reboot checks used the
existing source installation, not a portable replacement. Native GNOME Wayland,
portable suspend/resume, and live portable helper migration/action checks remain pending.
A separate system-wide libinput finger-calibration pilot passed boot-time login,
lock-screen accuracy, suspend/resume, all four rotations and pen/eraser regression
checks on this device. Its nine-target maximum error was 9.63 pixels. The app now provides a
**Calibrate for login and desktop** workflow for system-wide libinput calibration
on Ubuntu and Fedora, with installation, reboot verification and restore.
The integrated workflow still needs physical acceptance on both distributions;
the device pilot validated the underlying configuration.
See [validation and release status](docs/VALIDATION.md) for scope and remaining work.

## Portable app (no Python installation)

The portable x86_64 package includes Python, Qt, D-Bus bindings and the native
command-line utilities used by the fixes. Extract `toughbook-tools-*-linux-x86_64.tar.gz`,
open its directory, and run `./toughbook-tools`. Run `./toughbook-tools --install`
to add it to your application menu. Keep the executable and `_internal` together.

The baseline is glibc 2.36 (Debian 12+, Ubuntu 24.04+, current Fedora/Arch).
Your kernel, graphics drivers and running desktop/audio services remain host
components. See [portable installation and building](docs/portable.md) for the
full boundary, licenses, corresponding sources and build command. Portable builds
are local artifacts until published; the source setup below remains available.

## Source setup: Toughbook Tools GUI

The setup tool targets **Debian-based systems (including Ubuntu), Fedora, and
Arch-based systems** using systemd. Use a local
**Wayland or X11** desktop or window manager. Desktop
names do not gate the fixes. Touch calibration selects KWin, X11 or the common
libinput rule workflow; buttons default to the dedicated input device rather
than requiring a shortcut portal. See [desktop compatibility](docs/desktops.md)
for action providers, login activation and compositor capabilities.

Install Git and Python first if needed:

| Family | Bootstrap command |
| --- | --- |
| Debian / Ubuntu | `sudo apt-get update && sudo apt-get install git python3` |
| Fedora | `sudo dnf install git python3` |
| Arch / derivatives | Update with `sudo pacman -Syu`, then `sudo pacman -S --needed git python` |

As your logged-in desktop user:

```sh
git clone https://github.com/the1glorfindel/toughbook-linux-tools.git
cd toughbook-linux-tools
python3 tools/setup-linux.py --dry-run
python3 tools/setup-linux.py
python3 toughbook-tools.py --status
```

The read-only preview lists the native package command. Setup detects the
family from `/etc/os-release`, installs dependencies through APT, DNF or Pacman,
and installs the per-user menu launcher. Use `--desktop kde`, `--desktop gnome` or `--desktop generic`
to choose integration packages explicitly; other desktops select generic by default. Open **Toughbook Tools** from your application
menu. Rerun setup after `git pull` to update the installed copy.

Setup uses distribution PySide6 packages when available. On Debian-based releases
without them, it installs PySide6 in a persistent virtual environment under
`~/.local/share/toughbook-tools-python` (or `$XDG_DATA_HOME`). Keep that environment;
the menu launcher records its interpreter. `bash tools/setup-ubuntu.sh` remains a
compatibility alias. See [Linux installation and compatibility](docs/linux.md)
for dependencies, audio-session setup and kernel-header differences.

The optional tablet-button driver is separate. Setup does not install or load
it. Add `--driver-prerequisites` to install its build packages and running-kernel
headers, or use the Buttons page. Build-package installation may fail when
matching headers are unavailable; ordinary app setup does not require headers.
On GNOME 46, see the [optional manual keyboard extension](docs/gnome-keyboard.md)
if the built-in keyboard appears automatically after finger touch in laptop use.
If Secure Boot is enabled, follow the [signing guide](docs/driver-installation.md)
before loading the driver, then enable the button helper in the Buttons page.

For calibration on both the login screen and desktop, choose **Calibrate for
login and desktop** on the Finger touch page. Save the candidate, select it, use
**Apply candidate**, reboot, then select **Verify after login**. Administrator
authorization is requested only when installing/restoring system configuration.
See [system-wide calibration](docs/screen-calibration.md#system-wide-login-and-desktop-calibration).

Calibrate with only the internal display active, in normal landscape at 100%
scale. Audio repair requires a working PipeWire/Pulse compatibility server and
WirePlumber session; unplug wired headphones before testing. Expand
**Troubleshooting output** to inspect operation results.

Fedora KDE and Ubuntu 24.04 GNOME X11 on the reference CF-19 have physical
validation evidence. See [validation results](docs/VALIDATION.md) for measured
touch accuracy, tested workflows and remaining checks. Clean distribution setup,
Debian/Arch hardware acceptance and additional Ubuntu desktops remain pending.
Distribution coverage does not broaden the hardware scope in the table above.

## Independent scripts

Each tool also runs directly from the project directory:

| Script | Purpose | Detailed guide |
| --- | --- | --- |
| `python3 calibrate-screen.py` | Finger-touch calibration and restore | [Touchscreen](docs/screen-calibration.md) |
| `python3 fix-audio.py` | Speaker repair and restore | [Audio](docs/audio-fix.md) |
| `python3 toughbook-buttons.py` | Button settings, status, monitor, and helper | [Tablet buttons](docs/tablet-buttons.md) |

Run any script with `--help` for its command options. The optional button
driver can also be installed independently; see the [driver guide](docs/driver-installation.md).
For an overall status check, run `python3 toughbook-tools.py --status`.
To remove the GUI and its session integration, run
`python3 toughbook-tools.py --uninstall`; saved settings and backups remain.

For causes, detailed setup, and troubleshooting, start with the
[documentation index](docs/README.md).

See [third-party notices](THIRD_PARTY.md) and the [changelog](CHANGELOG.md).
