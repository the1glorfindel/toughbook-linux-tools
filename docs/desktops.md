# Desktop-independent fixes

The application no longer requires a KDE/GNOME desktop name. It detects the
running session and compositor interfaces, not which desktops happen to be
installed. Setup uses `--desktop generic` automatically for other environments;
KDE/GNOME selections only add their integration packages.

Hardware scope remains the CF-19 Mk6 and the specific finger sensor, codec and
tablet-button device described in the README. New session backends have automated
coverage; physical validation on additional desktops remains pending.

| Feature | Common path | Optional desktop integration |
| --- | --- | --- |
| Speaker fix | ALSA, PipeWire and WirePlumber, independent of shell | None required |
| Tablet-button driver | Kernel ACPI/input and dedicated-device udev rule | None required |
| Button delivery | Direct evdev reading of the dedicated four-button device | Global Shortcuts portal can be selected explicitly |
| Touch calibration | Native X11 device matrix or persistent libinput udev rule | KWin live preview; Mutter display discovery |
| Button assignments | Executable, shell command or installed application | Built-in actions use detected interfaces/providers |

## Setup and session startup

Run `python3 tools/setup-linux.py` from your graphical session. Unknown desktop
names select generic packages; `--desktop generic` also selects them explicitly.
X11 dependencies include xinput/xrandr and native Qt plugin libraries; generic Wayland output discovery uses
native Qt. Setup includes a generic portal backend for dialogs, but direct button
delivery does not require the Global Shortcuts portal.

Enable the button helper on the Buttons page. Its XDG autostart entry imports
the current display/session environment before restarting the user service.
Window managers without XDG autostart must run
`python3 toughbook-buttons.py --start-session` from their session startup file
(after installing the helper once). The application still uses a systemd user
service; this change removes desktop-shell requirements, not the systemd dependency.

## Finger touch

Use the internal display alone, at the origin, at 100% scale in normal landscape.
Do not rotate or change the display layout during measurement or verification.

- **KWin Wayland:** existing live calibration, preview and rollback remain.
  Detection probes the running KWin service, including when another desktop
  name is set in the environment.
- **Native X11 (Xfce, MATE, Cinnamon, LXQt, window managers, KDE/GNOME X11):**
  match the discovered finger node against XInput's `Device Node` property.
  Only that device's Coordinate Transformation Matrix changes. Accepting saves
  a login activation record and XDG autostart entry; cancellation or a failed
  save restores the previous matrix. Pen devices are excluded. Window managers
  without XDG autostart can run `calibrate-screen.py --activate` after X startup.
  Activation refuses a changed display layout; return to the calibration layout
  first. Rotation bindings adjust display and finger coordinates together.
- **Other libinput-based Wayland compositors, including GNOME:** the Qt page
  measures a candidate without a live change. Save it, select **Apply candidate**,
  approve administrator authorization, log out/in and select **Verify after login**.
  The narrow udev rule sets libinput's default calibration. Verification requires
  a new login, the expected udev matrix and actual target taps. It does not claim
  success merely because a file was written. The standalone CLI offers the same
  measure/apply/verify/restore workflow.

A compositor can override libinput defaults. Restore/remove any conflicting
compositor-specific touchscreen transform before using the common rule path.
Unknown or synthetic output names, multiple outputs, scaling and changed geometry
are refused rather than guessed. The GUI uses native Qt for measurement and verification; the terminal CLI
can also use `--verify BACKUP --qt`. The Qt helper queries native Wayland, not an
XWayland virtual display. Existing GNOME and KWin recovery backups remain readable.
Switching between a KWin-specific matrix and a system libinput rule requires
restoring the old backend first to avoid composing two independent corrections.

## Tablet-button delivery

The default **Dedicated tablet device** backend reads only the named
`Panasonic CF-19 Tablet Buttons` event node with `MAT001F` ancestry. It never opens
or grabs the ordinary keyboard, never uses root, and ignores all keys except
F13–F16. The driver-provided uaccess rule grants active-session access. Do not
join the broad `input` group. A single helper lock prevents duplicate daemons.
The helper exclusively grabs this dedicated four-key device after revalidating
the opened descriptor's driver name and ACPI ancestry. This prevents desktop
defaults such as GNOME's `XF86Tools` shortcut from also opening Settings.
Stopping the helper closes the descriptor and releases exclusive access.
On GNOME, the Keyboard action toggles automatic on-screen-keyboard availability;
touch a text-entry field with a finger to show it after enabling it.

Actions run only for one identifiable, active, local, unlocked graphical login
owned by the current user. Ambiguous, inactive, remote or locked sessions suppress
actions. Press/release tracking suppresses held repeats; dropped input batches
are discarded. Disconnects trigger reconnection to the dedicated device.
Identification pauses actions, with automatic timeout recovery.
While the helper runs, identification receives named press/release events over
its session D-Bus interface, leaving the dedicated device exclusively held.
Without a helper, the command-line monitor reads the dedicated evdev node directly.

Choose **Desktop shortcut portal** and restart the helper to retain the previous
compositor-approved shortcut behavior. Portal support and key conflicts then
depend on that backend. Both delivery modes use the same saved assignments.
Do not independently bind the same physical buttons in the desktop's own settings
while using direct mode, or both configurations may run an action.

CLI selection is also available:

```sh
python3 toughbook-buttons.py --install --backend direct
python3 toughbook-buttons.py --install --backend portal
```

## Built-in action capabilities

- **Lock:** try screen-saver D-Bus interfaces, then logind's current-session lock
  request. A lock request requires a functioning session locker; logind does not
  draw a lock screen. Configure a locker first, or assign its executable.
- **Keyboard:** KWin's virtual keyboard or GNOME's accessibility keyboard when
  available. Other X11 sessions can use installed Onboard or Matchbox Keyboard;
  compatible Wayland compositors can use installed wvkbd. The helper toggles the
  provider process it launches. These providers are optional and are not installed
  automatically; compositor protocol support still matters. Otherwise assign the
  command for the keyboard configured in that session.
- **Application launcher:** use KWin/Plasma or GNOME Shell when available,
  otherwise an installed fuzzel, wofi, rofi, Xfce app finder, MATE run dialog or
  LXQt runner. Choose an installed application/command directly if no launcher
  is configured.
- **Rotation:** KScreen, Mutter, native XRandR with matching finger rotation,
  or `wlr-randr` on compositors exposing its output-management protocol. Changes
  are read back and failures attempt rollback. Unknown protocols and reflected
  transforms are refused. For another compositor, assign its own rotation command
  and ensure that command preserves touchscreen mapping.

There is no promise that every compositor implements the same output-management,
virtual-keyboard or launcher protocol. Missing capabilities produce an actionable
message; arbitrary commands remain available on every supported graphical session.
A missing rotation/keyboard provider does not prevent the audio fix, button driver,
button delivery, custom assignments or calibration from working.

## Verification evidence

Native Qt clients pass the isolated X11 (Xvfb/Openbox) and Wayland (headless
Weston, without XWayland) checks. The full automated suite also passes under
both explicit session types. X11 matrix apply/read-back/restore was exercised on
a synthetic pointer, and Wayland 180° output metadata was verified. See
[validation status](VALIDATION.md) and [repeatable smoke checks](development.md).
Physical CF-19 acceptance remains separate. Native X11 fullscreen targets require
a fullscreen-capable window manager; an X server alone is insufficient.

## References

- [libinput static calibration defaults](https://wayland.freedesktop.org/libinput/doc/latest/device-configuration-via-udev.html)
- [Global Shortcuts portal](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.GlobalShortcuts.html)
- [XInput](https://www.x.org/releases/current/doc/man/man1/xinput.1.xhtml)
- [XRandR](https://www.x.org/releases/current/doc/man/man1/xrandr.1.xhtml)
