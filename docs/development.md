# Development and source archives

## Run checks

Install the GUI dependencies from the main README first. From the repository root:

```sh
python3 -m unittest discover -s tests -v
```

The suite uses mocks and temporary state for desktop, audio, device discovery,
and rollback behavior; it does not prove physical hardware behavior. Some tests
also use available system tools such as a C compiler and udev/systemd validators.
The portable driver decoder test is part of the suite and compiles with
`-std=c99 -Wall -Wextra -Werror` when a compiler is available.

For a direct decoder check:

```sh
cc -std=c99 -Wall -Wextra -Werror -o /tmp/test-hbtn driver/test-hbtn-decode.c
/tmp/test-hbtn
```

Building/loading the kernel module is a separate, Fedora-kernel-specific check;
see [driver installation](driver-installation.md). Physical button, display,
touch, sound, suspend, and login checks are recorded in
[validation status](VALIDATION.md).

## Build and inspect a source archive

```sh
python3 tools/make-release.py
python3 -m unittest discover -s tests -p test_release.py -v
```

The archive is written beside the repository by default, with a SHA-256 file.
The builder allowlists source and test files, all Markdown under `docs/`, the
driver sources/license/build files, desktop integration templates, and the app icon.
It omits Git metadata, bytecode, and runtime state, and normalizes timestamps
and ownership for reproducibility. The release test checks repeatability,
required content, extracted command-line help, and absence of local home paths.

No command here publishes an archive or changes a Git tag.
