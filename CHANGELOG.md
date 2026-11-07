# Changelog

## 0.0.1

- Package the CF-19 Mk6 screen and speaker fixes as shell-independent Python tools.
- Preserve the tested nine-point KDE Wayland calibration and add a GNOME
  libinput/udev backend with a separate apply/login/verify workflow.
- Detect hardware and internal outputs instead of using a particular username,
  event number, ALSA card index, output connector name, or PCI address.
- Preserve private backups outside the source tree, provide explicit undo, and
  retain the original audio uninstall baseline on repeat installations.
- Document Fedora dependencies, observed causes, implementation details,
  recovery, and upstream licensing of runtime-generated profiles.
- Add isolated tests and a deterministic source-archive builder.

GNOME physical validation and clean-install validation remain pending. This is a
early release, not a claim that all CF-19 revisions or desktop layouts work.

## Unreleased

- Add experimental CF-19 tablet-button driver and per-user GTK4 settings/helper
  using the Global Shortcuts portal; customizable actions and Wayland adapters.
- Add DKMS setup/removal documentation and simulated tests. Target kernel build
  and all physical button/rotation/session acceptance checks remain required.
- Preserve version 0.0.1 and existing release tag.
