# Third-party notices

Project Python code and documentation are MIT licensed; see LICENSE.
No vendored Python packages, kernel sources, or upstream mixer profile files
are included in the source release.

The audio tool reads and modifies copies of the **installed** PipeWire ALSA Card
Profile files at runtime. Those files originate from the PulseAudio/ACP codebase
and contain upstream copyright and GNU LGPL notices. Generated copies preserve
those notices and do not become MIT licensed merely because this tool generates
them. Consult the header of each generated file and the installed Fedora package
license information before redistributing generated configurations. They are
runtime state and are excluded from the release archive.

Python, Tk, dbus-python, PipeWire, WirePlumber, ALSA, libkscreen, XWayland,
systemd-udev, and sudo are separate system dependencies under their own licenses.
This archive does not distribute them. Links to their relevant implementation
and configuration documentation appear in the issue explanations.
