#!/usr/bin/env python3
"""Build a self-contained x86_64 runtime with a rootless Podman/Docker build container."""
import argparse
import os
import platform
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', default=shutil.which('podman') or shutil.which('docker'))
    parser.add_argument('--output-dir', type=Path, default=ROOT/'dist')
    parser.add_argument('--work-dir', type=Path, help='Build workspace (default: temporary directory)')
    args = parser.parse_args()
    if not args.engine:
        parser.error('Install Podman or Docker, or select --engine /path/to/engine.')
    if platform.machine() != 'x86_64':
        parser.error('This portable build currently targets x86_64.')
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    image = 'localhost/toughbook-tools-builder:bookworm'
    subprocess.run([args.engine, 'build', '--network=host', '-t', image, '-f', str(ROOT/'bundle/Containerfile'), str(ROOT)], check=True)
    revision = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip() or 'source-archive'
    with tempfile.TemporaryDirectory(prefix='toughbook-freeze-') as temporary:
        work = args.work_dir.resolve() if args.work_dir else Path(temporary)
        work.mkdir(parents=True, exist_ok=True)
        options = ['--cgroups=disabled'] if Path(args.engine).name == 'podman' else ['--user', f'{os.getuid()}:{os.getgid()}']
        subprocess.run([args.engine, 'run', '--rm', '--network=host', '--security-opt', 'label=disable', *options,
                        '-v', f'{ROOT}:/src:ro', '-v', f'{output}:/output', '-v', f'{work}:/work',
                        '-e', 'TOUGHBOOK_REVISION=' + revision, image, '/opt/build-python/bin/python',
                        '/src/bundle/build.py'], check=True)
    # A fresh base image has no Python, Qt or client packages. Catch libraries
    # that the freezer silently considered system dependencies on the builder.
    import sys
    sys.path.insert(0, str(ROOT))
    from toughbook import __version__
    application = output/f'toughbook-tools-{__version__}-linux-x86_64'
    subprocess.run([args.engine, 'run', '--rm', '--network=none', '--security-opt', 'label=disable', *options,
                    '-v', f'{application}:/app:ro', 'docker.io/library/debian:bookworm-slim',
                    '/bin/sh', '-ec',
                    '! command -v python3; /app/toughbook-tools --tool check-runtime; '
                    'for tool in pactl pw-play amixer alsactl xinput xrandr; do '
                    '/app/toughbook-tools --exec-tool "$tool" --help >/dev/null 2>&1; done; '
                    # wlr-randr 0.2 connects before parsing --help. No compositor is running here.
                    '/app/toughbook-tools --exec-tool wlr-randr --help >/tmp/wlr.log 2>&1 || '
                    'grep -q "^failed to connect to display$" /tmp/wlr.log'], check=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
