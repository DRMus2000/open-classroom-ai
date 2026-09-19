"""Build a complete portable ZIP from an explicit source/runtime allowlist."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile


def build(runtime, output):
    source = Path(__file__).resolve().parents[1]
    runtime, output = Path(runtime).resolve(), Path(output).resolve()
    if not (runtime / 'python/python.exe').is_file():
        raise ValueError('complete portable runtime is required')
    if output.exists():
        raise ValueError('release output already exists; choose a new versioned filename')
    for root in (source / 'app', source / 'web', source / 'scripts', source / 'examples', source / 'baseline', runtime):
        if root == output.parent or root in output.parents:
            raise ValueError('release output must not be inside an input tree')
    output.parent.mkdir(parents=True, exist_ok=True)
    selected = {}
    for root, prefix in ((source / 'app', 'app'), (source / 'web', 'web'),
                         (source / 'scripts', 'scripts'), (source / 'examples', 'examples'),
                         (source / 'baseline', 'baseline'), (source / 'launchers', ''), (runtime, 'runtime')):
        for path in root.rglob('*'):
            if path.is_symlink():
                raise ValueError('release does not follow symlinks')
            relative = path.relative_to(root)
            if not path.is_file() or '__pycache__' in relative.parts or path.suffix in {'.pyc', '.pyo', '.log'}:
                continue
            if path.name in {'.env', '.webui_secret_key', 'bridge.key'}:
                raise ValueError('unexpected credential file in release input')
            selected[(Path(prefix) / relative).as_posix()] = path
    for filename in ('README.md', 'TEACHER_GUIDE_CN.md', 'IMPLEMENTATION_STATUS.md', 'PATCH_2.1.8_README.md', 'compatibility.json', 'requirements-runtime.lock'):
        selected[filename] = source / filename
    for filename in ('Open WebUI LICENSE.txt', 'Open WebUI LICENSE NOTICE.txt'):
        candidate = runtime.parent / filename
        if not candidate.is_file():
            raise ValueError('native license notices are required')
        selected[filename] = candidate
    hashes = {}
    prefix = 'openwebui-classroom-windows-x64/'
    try:
        with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as archive:
            for index, (name, path) in enumerate(sorted(selected.items())):
                digest = hashlib.sha256()
                with path.open('rb') as original, archive.open(prefix + name, 'w', force_zip64=True) as target:
                    for chunk in iter(lambda: original.read(1024 * 1024), b''):
                        digest.update(chunk); target.write(chunk)
                hashes[name] = digest.hexdigest()
                if index % 5000 == 0:
                    print('packaged', index, 'of', len(selected), flush=True)
            manifest = {'format_version': 2, 'contains_live_data': False, 'contains_credentials': False,
                        'open_webui': '0.11.2', 'python': '3.11.9', 'files': hashes}
            archive.writestr(prefix + 'release-manifest.json', json.dumps(manifest, indent=2))
        with zipfile.ZipFile(output) as archive:
            if archive.testzip():
                raise ValueError('release CRC verification failed')
        digest = hashlib.sha256()
        with output.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        output.with_suffix(output.suffix + '.sha256').write_text(digest.hexdigest() + '  ' + output.name + '\n', encoding='ascii')
        print(json.dumps({'archive': str(output), 'files': len(hashes), 'sha256': digest.hexdigest(), 'bytes': output.stat().st_size}))
    except Exception:
        # Only the newly created output of this invocation may be removed.
        output.unlink(missing_ok=True)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    build(args.runtime, args.output)
