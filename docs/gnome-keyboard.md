# GNOME 46 keyboard on the CF-19

GNOME 46 can show its built-in keyboard after touchscreen input even when
`screen-keyboard-enabled` is false. Its keyboard manager enables the keyboard
when the session is in touch mode and the last pointer input was touchscreen.
This CF-19 installation exposes no tablet-mode switch, so the tools cannot
reliably infer whether the display is folded over the physical keyboard.

The optional `gnome-extension/manual-keyboard@toughbook-tools` extension
disables only that automatic touchscreen condition. The physical Keyboard
button still toggles GNOME's `screen-keyboard-enabled` setting, so it remains
an explicit way to make the keyboard available. The extension is limited to
GNOME Shell 46 because it uses that version's internal keyboard manager API.

Build the extension bundle from the source root:

```sh
gnome-extensions pack -o /tmp gnome-extension/manual-keyboard@toughbook-tools
gnome-extensions install /tmp/manual-keyboard@toughbook-tools.shell-extension.zip
```

Log out and back in if GNOME does not list the new extension immediately, then
enable `manual-keyboard@toughbook-tools` using the Extensions app or
`gnome-extensions enable manual-keyboard@toughbook-tools`. Set
`screen-keyboard-enabled` to false for the default hidden state. Disable the
extension to restore GNOME's automatic touchscreen behavior. A GNOME Shell
upgrade requires rechecking the extension against the new Shell version.
