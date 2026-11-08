# Ubuntu bring-up

Ubuntu support is prepared for the same CF-19 Mk6 hardware as the Fedora
release. It has not yet been physically tested on Ubuntu. Use a GNOME or KDE
Wayland session; X11 and other CF-19 revisions remain outside the supported
workflow.

## Install

From a fresh Ubuntu desktop, as the logged-in user:

```sh
sudo apt-get update
sudo apt-get install -y git
git clone https://github.com/the1glorfindel/toughbook-linux-tools.git
cd toughbook-linux-tools
bash tools/setup-ubuntu.sh
python3 toughbook-tools.py --status
```

Open **Toughbook Tools** from the application menu after setup finishes.

The script uses APT for Python, D-Bus, Tk, XWayland, PipeWire, WirePlumber,
ALSA, portal, DKMS, compiler, Secure Boot, and matching kernel-header packages.
It installs PySide6 from APT when available. Ubuntu 24.04 lacks that package,
so the script creates a persistent virtual environment with access to Ubuntu's
system `dbus` and `gi` Python modules and installs PySide6 there. The application
menu entry uses the selected interpreter.

If matching headers are unavailable for the running kernel, the GUI and
standalone tools can still install, but the optional button driver cannot be
built until the corresponding `linux-headers-$(uname -r)` package or kernel
header tree is available. Reboot into a packaged Ubuntu kernel if needed.

Run `python3 toughbook-tools.py --status` for a read-only hardware check, then
launch **Toughbook Tools** from the application menu. The touchscreen and
button actions need a local Wayland desktop session. The audio repair also
requires that the card be managed by PipeWire and WirePlumber; it will inspect
the installed profile format before changing audio settings.

## Distribution differences

- The optional DKMS installer checks `/lib/modules/$(uname -r)/build`, which
  works with Ubuntu's `linux-headers-*` and Fedora's `kernel-devel-*` layouts.
- The Buttons page uses APT on Ubuntu and DNF on Fedora for driver build
  prerequisites. It never replaces another driver bound to `MAT001F`.
- Ubuntu 24.04 ships WirePlumber 0.4, whose ALSA rules are Lua fragments under
  `~/.config/wireplumber/main.lua.d/`. Newer WirePlumber 0.5 uses `.conf`
  fragments under `~/.config/wireplumber/wireplumber.conf.d/`. The audio tool
  selects the format from `wireplumber --version` and retains exact backups.
- KDE needs `kscreen-doctor`; the setup script installs the package that
  supplies it when run in a KDE session. GNOME display discovery uses D-Bus.

## First checks after switching

1. Confirm the CF-19 revision, Wacom finger interface, Realtek codec, and
   `MAT001F` device with `python3 toughbook-tools.py --status`.
2. Verify the session is Wayland (`echo "$XDG_SESSION_TYPE"`) and only the
   internal display is active before calibrating finger touch.
3. Test speaker playback and its restoration workflow before saving a repair.
4. Check whether an Ubuntu kernel driver already owns `MAT001F`. Install the
   optional driver only if the Buttons page reports no competing binding.
5. If Secure Boot is enabled, follow [MOK enrollment](driver-installation.md)
   before loading the DKMS module.

Keep the Fedora installation and its saved backups available until Ubuntu's
display, audio, button, suspend, and login behavior has been checked in person.
