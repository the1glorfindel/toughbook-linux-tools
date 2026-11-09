#!/usr/bin/env python3
"""Build and inventory an offline portable runtime inside the build container."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

from sources import upstream, native, digest, index

ROOT = Path(__file__).resolve().parents[1]


def execute(argv, **kwargs):
    print('+ ' + ' '.join(map(str, argv)), flush=True)
    subprocess.run(list(map(str, argv)), check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=Path('/output'))
    parser.add_argument('--work-dir', type=Path, default=Path('/work'))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.work_dir.mkdir(parents=True, exist_ok=True)
    upstream(args.work_dir)
    env = {**os.environ, 'PYTHONPATH': str(ROOT), 'PYINSTALLER_CONFIG_DIR': str(args.work_dir/'cache'), 'TOUGHBOOK_METADATA_DIR': str(args.work_dir/'metadata')}
    execute([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--distpath', args.work_dir/'dist',
             '--workpath', args.work_dir/'freeze', ROOT/'bundle/toughbook.spec'], env=env, cwd=ROOT)
    app = args.work_dir/'dist/toughbook-tools'
    execute([app/'toughbook-tools', '--tool', 'check-runtime'], env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'})
    for tool in ('app', 'screen', 'audio', 'buttons', 'check-display'):
        execute([app/'toughbook-tools', '--tool', tool, '--help'])
    manifest = json.loads((app/'_internal/BUNDLE-MANIFEST.json').read_text())
    name = f"toughbook-tools-{manifest['version']}-linux-{manifest['architecture']}"
    native(manifest, args.work_dir)
    # Include the application's corresponding source and build recipe as well.
    import importlib.util
    spec = importlib.util.spec_from_file_location('source_builder', ROOT/'tools/make-release.py')
    source_builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(source_builder)
    source_builder.build(args.work_dir/'sources')
    index(manifest, args.work_dir)
    sources_archive = args.output_dir/(name + '-sources.tar.gz')
    with tarfile.open(sources_archive, 'w:gz') as stream:
        stream.add(args.work_dir/'sources', arcname=name+'-sources')
    sources_archive.with_suffix('.gz.sha256').write_text(digest(sources_archive) + '  ' + sources_archive.name + '\n')
    final = args.output_dir/name
    if final.exists():
        shutil.rmtree(final)
    shutil.copytree(app, final, symlinks=True)
    manifest['corresponding_source_archive'] = sources_archive.name
    manifest['corresponding_source_sha256'] = digest(sources_archive)
    (final/'_internal/BUNDLE-MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (final/'README-portable.txt').write_text(
        'Toughbook Tools portable runtime\n\nRun ./toughbook-tools to open the app.\n'
        'Run ./toughbook-tools --install to copy the complete runtime into your user application directory.\n'
        'Keep the executable and _internal directory together. No Python or pip installation is needed.\n'
        'See _internal/docs/portable.md and --bundle-info for host service requirements and licenses.\n')
    hashes = []
    for path in sorted(final.rglob('*')):
        if path.is_file() and not path.is_symlink():
            hashes.append(hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + str(path.relative_to(final)))
    (final/'FILES.sha256').write_text('\n'.join(hashes) + '\n')
    archive = args.output_dir/(name + '.tar.gz')
    with tarfile.open(archive, 'w:gz', dereference=False) as stream:
        stream.add(final, arcname=name)
    archive.with_suffix('.gz.sha256').write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + '  ' + archive.name + '\n')
    print('Portable archive: ' + str(archive), flush=True)


if __name__ == '__main__':
    main()
