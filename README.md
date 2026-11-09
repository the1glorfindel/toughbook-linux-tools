# Toughbook Tools for Linux

**Toughbook Tools** is a KDE/GNOME Wayland app for three Panasonic CF-19 Mk6
issues: inaccurate finger touch, silent internal speakers, and missing tablet
buttons. It guides calibration and speaker repair, manages the four button
assignments, and shows recovery options and troubleshooting output. The optional
button driver is GPL-2.0-only; the application is MIT licensed.

| Feature | Tested hardware | Desktop support |
| --- | --- | --- |
| Finger touch | Wacom `056a:0093` finger interface | KDE Wayland tested; GNOME experimental |
| Internal speaker | Realtek ALC269VC | PipeWire/WirePlumber; Fedora KDE workflow tested |
| Tablet buttons | CF-19 Mk6 board `CF19-6`, ACPI `MAT001F` | KDE Wayland tested; GNOME physical validation pending |

Other CF-19 revisions, X11, the active Wacom pen, other touch controllers, and
other audio codecs are outside the tested scope. The detailed
[documentation index](docs/README.md) explains each issue and its recovery path.

## Quick start: Toughbook Tools GUI

The setup tool targets **Debian-based systems (including Ubuntu), Fedora, and
Arch-based systems** using systemd. Use a local KDE Plasma or GNOME Wayland
session. The Qt touchscreen calibration page requires KDE; GNOME calibration
uses the experimental standalone CLI workflow below. Other desktops and X11
are outside the supported workflow.

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
and installs the per-user menu launcher. Use `--desktop kde` or `--desktop gnome`
if desktop detection is unavailable. Open **Toughbook Tools** from your application
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
If Secure Boot is enabled, follow the [signing guide](docs/driver-installation.md)
before loading the driver, then enable the button helper in the Buttons page.

Calibrate with only the internal display active, in normal landscape at 100%
scale. Audio repair requires a working PipeWire/Pulse compatibility server and
WirePlumber session; unplug wired headphones before testing. Expand
**Troubleshooting output** to inspect operation results.

Fedora KDE on the reference CF-19 has physical validation evidence. Debian,
Ubuntu, and Arch compatibility is prepared in code and automated tests; live
installation and hardware acceptance remain pending. Distribution coverage does
not broaden the hardware scope in the table above.

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
