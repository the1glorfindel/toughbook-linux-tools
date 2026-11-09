# Documentation

The unified per-user launcher is installed with `python3 toughbook-tools.py --install`
and removed with `python3 toughbook-tools.py --uninstall`. It packages this documentation,
source, scripts, and the optional driver together; it does not start the
optional button helper. See the project README for launcher status and page
selection options.

## Issue and feature guides

- [Linux installation and compatibility](linux.md): Debian/Ubuntu, Fedora and
  Arch setup, package mapping, session prerequisites and kernel headers.
- [Ubuntu bring-up](ubuntu.md): installation, distribution differences, and
  first-run checks after switching systems.

- [Finger-touch calibration](screen-calibration.md): why finger coordinates
  miss their targets, how KDE/GNOME calibration works, and recovery steps.
- [Internal-speaker repair](audio-fix.md): the observed mixer/profile cause,
  reversible PipeWire/WirePlumber repair, and audio troubleshooting.
- [Tablet buttons](tablet-buttons.md): desktop actions, customization, portal
  shortcuts, rotation, and session troubleshooting.
- [Tablet-button driver](driver-installation.md): missing ACPI binding, exact
  Mk6 firmware mapping, Debian/Fedora/Arch DKMS setup, Secure Boot, and driver recovery.

## Project notes

- [Validation and release status](VALIDATION.md): automated and physical
  validation evidence, known limits, and pending checks.
- [Development and archives](development.md): tests, source archive generation,
  and release-content checks.
- [Third-party notices](../THIRD_PARTY.md): application and kernel module
  licensing/provenance.
