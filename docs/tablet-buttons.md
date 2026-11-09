# Tablet buttons: driver and assignments

Toughbook Tools configures the four CF-19 Mk6 front buttons independently of the
desktop shell. The default helper reads the dedicated driver device; an optional
shortcut-portal mode retains the previous KDE/GNOME integration. Existing physical
validation is from Fedora 44 KDE Wayland; direct input and other desktop paths
still need the [acceptance checks](VALIDATION.md).

| Physical button | Default action | Driver key |
| --- | --- | --- |
| Keyboard | Toggle on-screen keyboard | F13 |
| Circle | Open application launcher | F14 |
| Screen / Rotation | Rotate internal display | F15 |
| Key | Lock session | F16 |

Brightness controls remain with the existing firmware/kernel driver. The optional
`panasonic-hbtn` module binds only the tested `MAT001F` / `CF19-6` hardware. See
[driver installation](driver-installation.md) for event mapping, DKMS, Secure Boot,
removal and recovery.

## Setup

From the repository root, run the shared [Linux setup](linux.md):

```sh
python3 tools/setup-linux.py
python3 toughbook-buttons.py --status
```

Install/load the optional driver using the Buttons page or driver guide, then
choose **Dedicated tablet device (all desktops)** and **Install / start login
helper**. This mode needs no portal shortcut approval. The equivalent CLI is:

```sh
python3 toughbook-buttons.py --install --backend direct
```

The installer copies the full application, writes a user service and XDG
autostart entry, and starts the helper. Startup imports the current display and
session environment before restarting the service. Window managers without XDG
autostart should run `python3 toughbook-buttons.py --start-session` in their
session startup file after installation. Do not run the helper as root.

Direct mode uses the dedicated input-device name plus `MAT001F` ancestry, and
accepts only F13–F16. It exclusively grabs the validated dedicated four-key device
to prevent duplicate desktop shortcuts, and releases it when the helper stops.
It does not open/grab the ordinary keyboard. The supplied
udev rule grants access to the active desktop user. Actions are suppressed unless
one active, local, unlocked graphical login belonging to that user is identified.
Disconnects are retried; held repeats and dropped event batches are ignored.
Debouncing a worn switch that produces multiple complete presses is not claimed.

## Assignments and identification

Each button can run a built-in action, installed `.desktop` application,
executable with arguments, explicit shell command, or no action. Settings are in
`$XDG_CONFIG_HOME/toughbook-buttons/settings.json` (normally `~/.config/...`).
The helper reads them on each press. Missing applications and command failures
are reported without clearing the other assignments.

Plain commands are parsed into argument vectors. Pipes and redirection require
the explicit **Shell command** type. Existing custom assignments are retained
when changing delivery backend or removing/reinstalling application integration.

**Identify physical buttons** pauses actions and starts a monitor on the dedicated
device. Stop identification to resume; the pause also expires after 60 seconds.
Independent monitoring is available with `python3 toughbook-buttons.py --monitor`.
Driver scan codes and paired press/release events are described in the driver guide.

## Optional portal mode

Select **Desktop shortcut portal** and restart the helper, or run:

```sh
python3 toughbook-buttons.py --install --backend portal
```

This keeps a Global Shortcuts portal session alive in the user helper. It requires
a supporting compositor/backend and desktop approval. Install the appropriate
portal backend, log out/in if necessary, and use **Configure shortcuts** to resolve
conflicts. Installing a portal package alone does not prove support. Choose direct
mode when the compositor lacks this portal.

The Linux keys F13–F16 may appear as Tools / Launch (5), Launch (6), Launch (7)
or `XF86Tools`, `XF86Launch5`, `XF86Launch6`, `XF86Launch7` in the desktop dialog.
The GUI/status shows actual approved bindings. Another keyboard producing the
same keysym can activate a portal binding; direct mode accepts only the dedicated
tablet node. Remove separate desktop bindings for the same physical keys when
using direct mode, so two independent configurations do not both run actions.

## Desktop actions

See [desktop compatibility](desktops.md) for the complete capability list.
KWin and GNOME action interfaces remain available. Other desktops can use their
screen-saver/logind lock interface, installed launcher and keyboard providers,
XRandR rotation on X11, or `wlr-randr` output management on supporting Wayland
compositors. X11 rotation also composes the matching finger transform; failures
attempt to restore both display and input state.

Some compositors provide different rotation/keyboard protocols. Assign their
specific executable or installed application when a built-in provider is missing.
The app reports the missing capability instead of rejecting the entire desktop.
Keep only the internal display active for rotation and calibrate in normal
landscape. A lock request needs an actual configured session locker.

## Troubleshooting and removal

- **No dedicated device:** inspect `--status`, `modinfo panasonic-hbtn`, the
  `MAT001F` binding and kernel journal. Follow the driver guide; do not unbind
  another driver blindly.
- **Access denied:** verify the supplied narrowly matched uaccess rule, refresh
  only the tablet event device and log out/in. Never grant broad `input` group
  access or run the helper as root.
- **Direct mode shows the last button but runs no action:** confirm the local
  session is active and unlocked. Check logind registration and that only one
  graphical session is active for that user. Review the saved assignment and logs.
- **Portal unavailable/conflicting:** switch to direct mode or configure the
  installed compositor's Global Shortcuts backend and approve its bindings.
- **Provider missing or rotation failed:** choose the installed provider command;
  inspect troubleshooting output and saved display recovery data. If rollback
  also fails, use desktop display settings to return to the original orientation.
- **Login helper does not start:** inspect `systemctl --user status
  toughbook-buttons.service` and `journalctl --user -u toughbook-buttons.service -b`.
  Reinstall/start it from the local graphical session. For minimal window managers,
  add the `--start-session` invocation described above.

`python3 toughbook-tools.py --uninstall` removes the app/session integration and
retains preferences and recovery backups. Driver unload/removal is separate;
follow the driver guide. Existing physical Fedora/KDE portal validation remains
recorded in [validation status](VALIDATION.md); it does not validate new backends.
