# Linux installation and compatibility

The setup and dependency layer targets Debian-based distributions (including
Ubuntu and derivatives), Fedora and derivatives identifying it in `ID_LIKE`,
and Arch-based distributions such as Manjaro and EndeavourOS. Detection honors
`ID` before the ordered `ID_LIKE` compatibility hints in `/etc/os-release`.
RHEL compatibility alone is not treated as Fedora: repository/package availability
differs. Immutable Fedora variants (Silverblue/Kinoite), non-systemd derivatives,
other package managers need separate integration; automatic
setup targets traditional writable APT/DNF/Pacman desktop installations.

This changes distribution packaging, not hardware support. The reference hardware
remains the Panasonic CF-19 Mk6, Wacom `056a:0093` finger interface, Realtek
ALC269VC and `MAT001F` tablet buttons. KDE Wayland has hardware evidence from
Fedora; Ubuntu 24.04 GNOME X11 also has specific physical checks recorded in
[validation status](VALIDATION.md). Clean distribution setup and the remaining
acceptance checks are still pending. Other local Wayland and X11 desktops are supported through capability-based
backends. See [desktop compatibility](desktops.md) for calibration paths, direct
button input and optional action providers; new paths still need physical checks.

## Setup

Install Git, Python 3, and sudo using the distribution's package manager, with
administrator access configured for your desktop user. Clone the project and,
from the source root, run:

```sh
python3 tools/setup-linux.py --dry-run
python3 tools/setup-linux.py
python3 toughbook-tools.py --status
```

Use `--desktop kde`, `--desktop gnome` or `--desktop generic` to select
integration packages explicitly. Unknown desktop names use generic packages.
The preview makes no changes, and on Debian uses the current APT cache; actual
setup refreshes APT metadata before resolving candidates. Pacman setup uses
`-S --needed`, without refreshing databases, doing a full upgrade, or suppressing
conflict prompts. Keep Arch up to date with `sudo pacman -Syu` before setup;
never refresh databases alone and then install selected packages.

Setup installs application dependencies and the per-user menu launcher. It does
not enable the button helper, modify touch/audio settings, install or load the
kernel module, switch audio servers, enroll keys, or reboot. Its packages may
start distribution services through normal package-manager hooks. Run it as the
desktop user, not root. A polkit authentication agent is needed for GUI driver
controls; standard KDE/GNOME sessions normally provide one.

The old `bash tools/setup-ubuntu.sh` command delegates to this same installer.
Updates use `git pull` followed by setup again. APT/DNF/Pacman dependencies remain
installed after `python3 toughbook-tools.py --uninstall`; preferences and recovery
backups are also retained.

## Dependency mapping

The executable package lists live in `toughbook/distro.py`. The table highlights
packages whose names differ; setup includes supporting systemd, udev, D-Bus,
polkit, GLib/Gio and ALSA packages as well.

| Component | Debian / Ubuntu | Fedora | Arch |
| --- | --- | --- | --- |
| Qt Python | `python3-pyside6.qtwidgets` or private venv | `python3-pyside6` | `pyside6` |
| Qt Wayland | `qt6-wayland` (native Qt) | `qt6-qtwayland` | `qt6-wayland` |
| Python D-Bus / GI | `python3-dbus`, `python3-gi` | `python3-dbus`, `python3-gobject` | `python-dbus`, `python-gobject` |
| CLI calibration | `python3-tk`, `xwayland` | `python3-tkinter`, `xorg-x11-server-Xwayland` | `tk`, `xorg-xwayland` |
| KDE screen helper | `libkscreen-bin` or `libkf5screen-bin` | `libkscreen` | `libkscreen` |
| Playback / ACP profiles | `pipewire-bin` | `pipewire-utils`, `pipewire-libs` | `pipewire-audio`, `alsa-card-profiles` |
| `pactl` | `pulseaudio-utils` | `pulseaudio-utils` | `libpulse` |
| Mixer / test samples | `alsa-utils` | `alsa-utils` | `alsa-utils` |
| Session manager | `wireplumber` | `wireplumber` | `wireplumber` |
| Portal backend | `xdg-desktop-portal-kde`, `-gnome` or generic `-gtk` | same | same |
| Native X11 | `xinput`, `x11-xserver-utils` | `xinput`, `xrandr` | `xorg-xinput`, `xorg-xrandr` |
| Generic Wayland rotation | `wlr-randr` | `wlr-randr` | `wlr-randr` |

Debian/Ubuntu setup checks the APT candidate for PySide6. If unavailable (for
example on Ubuntu 24.04 or Debian 12), it creates a persistent venv with
`--system-site-packages` so distro D-Bus/GI modules remain available, and installs
PySide6 there with pip. Setup also installs the native XCB/graphics libraries
needed by wheel-based Qt on minimal X11 desktops (including `libxcb-cursor0`
and `libxkbcommon-x11-0`). Pip failure stops setup before launcher installation;
check network access, Python/wheel compatibility and enabled APT repositories.
Keep `~/.local/share/toughbook-tools-python` or its `$XDG_DATA_HOME` equivalent.
After a distribution Python upgrade, rerun setup to refresh the environment.
Native PySide6 is preferred on releases offering it, including Debian 13.

For common libinput calibration's dependency list and apply/login/verify flow, see the
[touch guide](screen-calibration.md). Optional shortcut-portal availability depends on
the installed compositor/backend version; installing a package does not establish
that all four shortcut actions work.

## Audio session prerequisite

A desktop may still use PulseAudio, especially on older Debian installations.
The repair is for PipeWire with WirePlumber and its PulseAudio compatibility
server. Check `pactl info` for a PipeWire server, and inspect:

```sh
systemctl --user status pipewire pipewire-pulse wireplumber
```

If needed, configure the distribution's supported PipeWire audio session first
(`pipewire-pulse` on these families), resolving any PulseAudio/session-manager
conflicts through its normal audio migration instructions. Setup installs tools
but deliberately does not replace a running audio stack. WirePlumber 0.4 uses
Lua rules; 0.5+ uses configuration fragments. The tool detects the installed
version and retains exact backups. Profile and sample files use standard paths;
unexpected profile contents stop the repair. See [audio repair](audio-fix.md).

## Optional driver and kernel headers

To add build tools without installing/loading the driver:

```sh
python3 tools/setup-linux.py --driver-prerequisites
```

The same package selection is used by the Buttons page's **Install prerequisites**
control. After its confirmation dialog, GUI Pacman uses `--noconfirm` because
there is no terminal; unresolved conflicts fail and must be handled manually.
CLI setup retains Pacman's normal interactive prompts. The driver installer requires `/lib/modules/$(uname -r)/build` to exist.

| Family | Header selection |
| --- | --- |
| Debian / Ubuntu | Exact `linux-headers-$(uname -r)`; old/custom kernels may need a matching repository or a reboot into a packaged kernel. |
| Fedora | Exact `kernel-devel-$(uname -r)`; reboot after installing a newer kernel if old development packages are unavailable. |
| Arch | Read `/usr/lib/modules/$(uname -r)/pkgbase` and install `<pkgbase>-headers`, e.g. `linux-headers`, `linux-lts-headers`, `linux-zen-headers`, `linux-hardened-headers`. |

Arch headers in rolling repositories follow the current packaged kernel, not
necessarily the kernel still running. After an upgrade, reboot into that kernel
before building. Missing/invalid `pkgbase` produces a clear error; custom or
third-party kernels need their matching headers installed manually. Setup does
not fetch AUR packages. If matching headers are unavailable, omit the optional
flag to install the application and handle the driver later.

The driver still restricts DMI/ACPI matching and refuses competing bindings.
Follow [driver installation](driver-installation.md) for DKMS, Secure Boot and
recovery. MOK enrollment applies to shim/MOK boot chains; Arch installations
using a different Secure Boot trust chain must sign with a key trusted by their
own kernel/firmware setup. Never assume a DKMS-generated key is already trusted.

## Package references

- [Debian PySide6 Widgets](https://packages.debian.org/trixie/python3-pyside6.qtwidgets)
  and [KDE screen helper](https://packages.debian.org/trixie/libkscreen-bin).
- [Arch PySide6](https://archlinux.org/packages/extra/x86_64/pyside6/),
  [PipeWire audio](https://archlinux.org/packages/extra/x86_64/pipewire-audio/),
  [ACP profiles](https://archlinux.org/packages/extra/x86_64/alsa-card-profiles/) and
  [KDE screen helper files](https://archlinux.org/packages/extra/x86_64/libkscreen/files/).
