# Third-party notices

Project Python code and documentation are MIT licensed; see LICENSE.
The `driver/` kernel module is GPL-2.0-only, separately from the MIT application.
See driver/README.md and driver/COPYING for provenance and terms. The source checkout does not vendor Python packages or upstream mixer profiles.
Portable runtime builds redistribute dependencies under their original licenses.

The audio tool reads and modifies copies of the **installed** PipeWire ALSA Card
Profile files at runtime. Those files originate from the PulseAudio/ACP codebase
and contain upstream copyright and GNU LGPL notices. Generated copies preserve
those notices and do not become MIT licensed merely because this tool generates
them. Consult the header of each generated file and the installed Fedora package
license information before redistributing generated configurations. They are
runtime state and are excluded from the release archive.

Python, PySide6/Qt6, Tk, dbus-python, PipeWire, WirePlumber, ALSA, libkscreen,
XWayland, XInput/XRandR, wlr-randr, systemd-udev, polkit, and sudo are separate system dependencies under
their own licenses.
The source archive does not distribute their binaries. The portable runtime
includes Python, PySide6/Qt, Tcl/Tk, D-Bus/GLib bindings, selected ALSA/PipeWire
clients and their libraries. Its `_internal/BUNDLE-MANIFEST.json` inventories
versions; `_internal/licenses` preserves package notices, common license texts,
and upstream Qt/PySide/ICU and build-tool notices. The matching `*-sources.tar.gz`
contains corresponding sources and build recipes with a SHA-256 index. Keep that
companion available with any redistributed runtime. Shared libraries remain
separate files; replacement must preserve a compatible ABI. Host kernel drivers,
services and compositor integrations are not part of that portable runtime.
Links to their relevant implementation
and configuration documentation appear in the issue explanations.
