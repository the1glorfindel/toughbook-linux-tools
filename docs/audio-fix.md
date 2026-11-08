# Silent internal speaker: issue and solution

## What was observed

The tested CF-19 Mk6 used the Intel HDA controller and Realtek ALC269VC codec.
`snd_hda_intel` and `snd_hda_codec_alc269` were already loaded. Fedora exposed an
analog stereo output, the Speaker and Master controls were enabled, and
Panasonic's separate firmware mute flag was off. Playback could run without
producing audible internal-speaker output.

The crucial observation was that enabling and raising the mixer control named
**Headphone** restored the **internal speaker**. This machine's speaker playback
therefore depends on a control whose name suggests it belongs only to headphones.
That is an observed behavioral dependency; the scripts do not claim to establish
the exact board wiring or a universal Realtek bug.

The standard ALSA Card Profile speaker path explicitly turns that control off:

```ini
[Element Headphone]
switch = off
volume = off
```

Manually unmuting it can work temporarily, but selecting the speaker route again
can mute it again. No new kernel module was required for the confirmed fix.

An earlier diagnostic used `speaker-test -D pulse`. The reference Fedora install
had no ALSA PCM with that name, so that test failed before playing. This was a
separate test-tool problem. The public script uses native `pw-play` instead.

## How the script fixes it

The script discovers the ALSA card behind PipeWire, validates the CF-19 model and
ALC269VC codec, and finds its analog stereo sink. It does not assume card 0,
`PCH`, or a particular PCI address. It backs up the current profile files, active
port, sink volume/mute, default output, and ALSA mixer state before testing.

With wired headphones unplugged, it selects the speaker, disables ALSA auto-mute,
and enables the Headphone control at 80% with output volume at 60%. These are test
levels, not fixed permanent loudness requirements. Native playback is directed
to that specific sink. Only an affirmative listening result advances installation.

The persistent change is a private speaker path that changes just the primary
Headphone element to:

```ini
[Element Headphone]
switch = mute
volume = merge
```

`switch = mute` lets normal route mute handling control this element instead of
forcing it off. `volume = merge` includes its gain in normal volume handling.
The rest of the distribution's installed path is retained, including upstream license text
and common directives. A private profile set replaces references to the standard
speaker path with this tool's path. A WirePlumber rule selects that profile set
only for the discovered internal card.

Files, relative to `$XDG_CONFIG_HOME` (normally `~/.config`):

```text
alsa-card-profile/paths/cf19-output-speaker.conf
alsa-card-profile/profile-sets/cf19.conf
wireplumber/wireplumber.conf.d/51-cf19-speaker.conf  # WirePlumber 0.5+
wireplumber/main.lua.d/51-cf19-speaker.lua           # WirePlumber 0.4
```

Only one of the two WirePlumber rule files is written. Ubuntu 24.04 supplies
WirePlumber 0.4; newer releases usually use 0.5. The tool checks the installed
version and chooses the matching format before making changes.

System files under `/usr/share` are untouched. The script restarts WirePlumber,
selects the private speaker port, sets it as default output, plays again, and
requires another affirmative listening result. Ordinary failure/cancellation
restores configuration, routing, and hardware mixer state. Saved files take
effect again on future logins, and normal volume/mute controls remain available.

## Run the repair

Install Fedora's playback and mixer tools, unplug wired headphones, and run the
status check before starting the interactive repair:

```sh
sudo dnf install python3 pipewire-utils pulseaudio-utils alsa-utils wireplumber
python3 fix-audio.py --status
python3 fix-audio.py
```

On Ubuntu, install the corresponding tools with:

```sh
sudo apt-get install pipewire-bin wireplumber pulseaudio-utils alsa-utils
python3 fix-audio.py --status
python3 fix-audio.py
```

Listen for both left/right test samples before answering each confirmation.
If either test is inaudible, answer no so the script can restore its snapshot.
The successful run restarts the user's WirePlumber service and selects the
internal speaker as the default output; other streams may pause briefly.

## Restore, updates, and limits

Every attempt retains a private JSON backup and adjacent `.alsa-state` file.
`--restore BACKUP` resolves the card again, restores/removes only the three tool
configuration files, restarts WirePlumber, and restores routing and mixer values.
Do not separate or delete the paired backup files. Repeated successful runs keep
the original uninstall baseline rather than replacing it with an already modified
configuration. Files that existed before the first run are restored verbatim.

An update cannot overwrite these per-user files, but it may change the upstream
defaults from which they were generated. Rerun the script after relevant PipeWire
updates to refresh private copies. Unexpected default-file formats cause a clean
stop rather than an assumed rewrite.

If this test remains silent, do not assume the kernel must be rebuilt: test wired
headphones, firmware/concealed-mode settings, hardware speaker health, and codec
routing. The stock driver supports additional pin overrides if diagnosis warrants
them, but this release neither performs pin retasking nor builds a module.

Headphone insertion/removal, suspend/resume, and persistence after a full reboot
remain acceptance checks for each machine. Speaker confirmation alone does not
prove those scenarios. Other CF-19 revisions and codecs may need different fixes.

## Troubleshooting

- **No matching card appears:** run `python3 fix-audio.py --status` and confirm
  Fedora detects the CF-19 ALC269VC codec. The tool deliberately rejects other
  codecs. Check that PipeWire/WirePlumber is running and install the README
  dependencies; do not guess a card number or edit system profile files.
- **The analog output is missing:** open the desktop Sound settings and select
  **Analog Stereo** for the internal card, then rerun `--status`. The script
  cannot test a route that PipeWire has not exposed.
- **First playback is still silent:** answer no to the listening prompt. The
  installation is abandoned and captured state is restored. Unplug headphones,
  check hardware/firmware mute settings, and confirm the internal speaker works
  outside this tool before retrying. This workaround does not repair a damaged
  speaker or identify board-level wiring.
- **WirePlumber fails to restart or the sink does not return:** inspect
  `journalctl --user -u wireplumber -b`. The script rolls back ordinary failed
  attempts; if recovery reports an issue, retain the printed backup and use
  `python3 fix-audio.py --restore BACKUP` after the service is healthy.
- **The profile files changed or an upstream update is reported:** the script
  recognizes only the speaker-path format it knows how to transform. It
  stops before rewriting unexpected files. Review the installed upstream
  profile/package update, then rerun the tool to regenerate the private copies;
  do not edit `/usr/share` files to bypass the check.
- **Headphones mute the internal speaker again:** auto-mute and jack-routing
  behavior is not established for every machine. Test with headphones unplugged
  and consult the audio guide's acceptance limits; this release does not claim
  universal headset switching behavior.
- **Restore says the mixer backup is missing:** keep the JSON backup beside its
  matching `BACKUP.alsa-state` file, and restore as the original user with the
  same `XDG_CONFIG_HOME`. A restore error may mean configuration files were
  restored but audio routing or mixer state still needs attention; read the full
  error and WirePlumber journal before retrying.

## Sources

- [PipeWire device properties and local ACP search directories](https://github.com/PipeWire/pipewire/blob/master/doc/dox/config/pipewire-props.7.md)
- [Upstream speaker path](https://github.com/PipeWire/pipewire/blob/master/spa/plugins/alsa/mixer/paths/analog-output-speaker.conf)
- [WirePlumber ALSA configuration](https://pipewire.pages.freedesktop.org/wireplumber/daemon/configuration/alsa.html)
- [Kernel HD-Audio reconfiguration documentation](https://docs.kernel.org/sound/hd-audio/notes.html)
