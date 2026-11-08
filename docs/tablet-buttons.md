# Tablet buttons: driver and assignments

The Toughbook Tools application configures CF-19 tablet buttons on KDE and GNOME Wayland.
**Hardware-tested on Fedora 44 KDE Wayland, CF-19 Mk6 (`CF19-6`).**
The four defaults, custom app launching, touch through all four orientations,
and suspend/resume were confirmed by the user. Calibration coefficients were
unchanged. Login autostart and saved assignments were also verified after
logout/login.
GNOME support is awaiting physical validation. Existing brightness handling,
audio configuration, and touch calibration coefficients are not rewritten.

The supported board is `CF19-6` (CF-19 Mk6). The ACPI `MAT001F` tablet device is separate from the ordinary keyboard and from
the existing Panasonic brightness driver. The missing binding explains why
these buttons can fail to appear in desktop shortcut settings. The new
`panasonic-hbtn` module has its own GPLv2 license; the settings application is MIT.
See [driver instructions](../driver/README.md) for the firmware decoding limits,
build, Secure Boot signing/enrollment, install and removal commands.

| Physical label | Windows meaning (model/configuration dependent) | Default Linux action |
| --- | --- | --- |
| Keyboard | On-screen keyboard | Toggle accessibility keyboard (F13) |
| Circle | Dashboard / application button | Launcher/search (F14) |
| Rotation | Display rotation | Cycle internal display orientation (F15) |
| Key | Windows security / Ctrl+Alt+Delete | Lock session (F16) |

The ordinary Enter key is unaffected. Press-and-hold assignments are deferred.

## Fedora setup

Install Fedora-packaged dependencies (no pip). This command includes the KDE
portal and driver build dependencies; follow the separate driver guide for
Secure Boot and module installation. GNOME uses its portal package instead of
the KDE backend and remains physically unvalidated.

```sh
sudo dnf install python3 python3-pyside6 qt6-qtwayland python3-gobject python3-dbus xdg-desktop-portal xdg-desktop-portal-kde libkscreen make gcc kernel-devel-$(uname -r) dkms mokutil openssl
```

On Ubuntu, run `bash tools/setup-ubuntu.sh` from the repository root instead;
it installs APT dependencies and the PySide6 environment. See
[Ubuntu bring-up](ubuntu.md).

For GNOME, replace `xdg-desktop-portal-kde` with
`xdg-desktop-portal-gnome`. The compositor must provide the Global Shortcuts
portal. Merely installing a package does not establish backend support: install
the driver as described in the [driver guide](driver-installation.md), inspect
`--status`, then install the per-user helper and approve its portal dialog. A
backend that does not expose this interface is reported as unavailable; there
is no fallback that captures your ordinary keyboard.

```sh
python3 toughbook-buttons.py --status
python3 toughbook-tools.py --install
python3 toughbook-tools.py --page buttons
```

Find **Toughbook Tools** in the application menu after installation. The private
installed copy lives under `$XDG_DATA_HOME/toughbook-tools`. Enable the button
helper from its page; it keeps its portal connection alive through a user service
started by the desktop autostart entry. Inspect logs with:

```sh
journalctl --user -u toughbook-buttons.service -b
```

The module emits Linux F13–F16. Fedora's default XKB map translates these to
`XF86Tools`, `XF86Launch5`, `XF86Launch6`, and `XF86Launch7`. The portal therefore
requests those desktop keysyms; they may be displayed as **Tools** and **Launch**
keys rather than F13–F16. The portal may ask you to approve or change these keys. The GUI/status show the
**actual** assigned trigger descriptions and unbound buttons, rather than assuming
requests were granted. Click **Configure global shortcuts…** to record your
physical buttons, especially after changing keyboard layouts or upgrading from
the provisional F13–F16 portal bindings. Resolve conflicts through your desktop shortcut settings
or the portal approval dialog. A portal shortcut can also be activated by another
keyboard producing the same desktop keysym; diagnostics, in contrast, read only the dedicated
tablet device. Authentication/lock screens may suppress portal shortcuts.

## Customize and identify

Each button selects a built-in action, installed desktop application, executable
with arguments, explicit shell command, or disabled action. Press **Save
assignments**; the running helper reads settings on each activation. Reset restores
the four defaults. Missing programs and failures appear in the app/session status
and logs without changing the other assignments.

Executable commands use argument parsing, not a shell. For example
`/usr/bin/printf "%s\\n" "two words"` keeps the last argument together. Pipes,
redirection, substitutions, and environment assignments require the explicit
**Shell command** choice. Commands run with the logged-in user's permissions in separate systemd scopes,
so stopping/uninstalling the button helper does not terminate launched applications.
Settings live at `$XDG_CONFIG_HOME/toughbook-buttons/settings.json`.

The app identifies the last portal activation live. To check the driver's actual
press/release events independently:

```sh
python3 toughbook-buttons.py --monitor
```

This reads only the named `MAT001F` tablet input device, never grabs it, ignores
repeat events, and requires the supplied narrowly matched uaccess rule. Do not
add your user to the broad `input` group. If access is denied, check rule installation
and log out/in; do not run the GUI/helper as root.

## Rotation and keyboard behavior

Initially only the internal LVDS/eDP/DSI display may be active. Disconnect or
disable external screens. Rotation uses KScreen or Mutter's display configuration
interface. Previous state is retained for recovery; a failed apply attempts to
restore it. Calibration values remain intact. Calibrated touch was physically verified through all four orientations on the
reference KDE Mk6. GNOME touch rotation remains unvalidated.
Keep a physical keyboard/touchpad available and restore normal orientation in
Display Settings if needed. Do not recalibrate while rotated.

GNOME toggles its accessibility keyboard setting. Enabling it may require focusing
an editable field before the keyboard appears. KDE needs its virtual keyboard
provider enabled in System Settings. Unavailable compositor methods produce an
error; no X11 keyboard automation or unrestricted GNOME Shell evaluation is used.

## Removal

```sh
python3 toughbook-buttons.py --uninstall
sudo bash driver/uninstall.sh
```

The first stops the helper and removes its service/autostart entries. To remove
the unified application and its menu entry too, run
`python3 toughbook-tools.py --uninstall`. Preferences are retained; delete
`$XDG_CONFIG_HOME/toughbook-buttons` manually to discard them. Existing calibration
and audio settings are separate and retained. Driver removal may require manual
unload or reboot, as described in its instructions.

## Troubleshooting

- **`--status` says the driver is not detected:** follow the checks in the
  [driver guide](driver-installation.md). The application cannot install or load
  the kernel module itself. Confirm the module is loaded and that this Mk6 has a
  `MAT001F` tablet device.
- **`--monitor` reports permission denied or shows no events:** run it as your
  desktop user, not with sudo. Confirm the installed udev rule and the dedicated
  device name in `python3 toughbook-buttons.py --status`, then reload the rules
  and refresh only that event device (replace `eventN` with the displayed event):

  ```sh
  sudo udevadm control --reload-rules
  sudo udevadm trigger --action=add /sys/class/input/eventN
  ```

  If access is still denied, log out/in to refresh the session ACL. Do not grant
  broad access to the `input` group. Unknown ACPI events belong in the
  driver/kernel diagnostics.
- **No shortcut approval appears, or the portal is unavailable:** install the
  portal backend for the current desktop (`xdg-desktop-portal-kde` or
  `xdg-desktop-portal-gnome`), then log out/in and inspect `--status`. The
  compositor must expose Global Shortcuts; the app does not fall back to
  monitoring the ordinary keyboard.
- **A button is unbound or the portal reports a conflict:** open the app's
  **Configure global shortcuts…** control and follow the desktop dialog. Clear
  stale custom keys first, then record each physical button in its named row.
  Fedora can display the requested triggers as Tools and Launch (5), Launch (6),
  and Launch (7), rather than F13–F16. Verify the actual trigger descriptions in
  the app/status; another keyboard generating the same keysym can invoke it too.
- **The trigger arrives but its action fails:** inspect the app status and
  `journalctl --user -u toughbook-buttons.service -b`. Check that the selected
  application or executable still exists. A plain command is parsed into argv;
  pipes and redirection work only when the assignment explicitly uses **Shell
  command**. A failed action does not clear other assignments.
- **Keyboard, launcher, or lock is unavailable:** enable a desktop virtual
  keyboard provider in KDE, or focus an editable field for GNOME's accessibility
  keyboard. Confirm the session is unlocked and the current desktop exposes the
  action interface. The helper reports unavailable methods; it does not use
  X11 automation or unrestricted GNOME Shell evaluation.
- **Rotation fails or touch is inaccurate:** use one active internal display and
  inspect desktop display settings. The action snapshots the current layout and
  attempts rollback on failure; if recovery also fails, restore the previous
  orientation in Display Settings and inspect helper logs. Do not recalibrate
  while rotated. KDE Mk6 touch was verified in all orientations; GNOME rotation
  remains physically unvalidated.
- **Buttons stop working after login:** check
  `systemctl --user status toughbook-buttons.service` and its journal. Re-run
  `python3 toughbook-buttons.py --install` from the desktop user, approve the
  portal request, and verify saved assignments in the app. Preferences are in
  `$XDG_CONFIG_HOME/toughbook-buttons/settings.json` and survive integration
  removal.

## Acceptance status

Verified on the reference Mk6: all four physical scan codes and paired releases,
working defaults, custom application launching through the GUI, conflict resolution,
all four orientations with accurate finger touch, session locking and suspend/resume.
The existing calibration matrix and output mapping remained unchanged. Driver
removal/reinstallation was exercised during bring-up; live per-user uninstall and
reinstall removed/restored the app and session entries while preserving preferences.
The target Fedora kernel build, portable C vectors and automated suite pass.

Login persistence is verified: the helper started automatically after logout/login,
restored all bindings and the saved Emoji Selector assignment, and the user confirmed
all buttons worked as before. Calibration remained unchanged. GNOME remains
simulated and awaiting physical validation. Press-and-hold timing and switch debounce are not claimed;
the helper ignores repeat activation while held. A worn button can still emit two
complete physical press/release cycles. Version 0.1.0 includes this feature; the existing v0.0.1 tag is preserved.

Interface references: [Global Shortcuts portal](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.GlobalShortcuts.html),
[Mutter DisplayConfig](https://gitlab.gnome.org/GNOME/mutter/-/blob/main/data/dbus-interfaces/org.gnome.Mutter.DisplayConfig.xml).
