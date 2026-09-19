"""Build the 2.1.8 code-only patch; never include runtime or installation data."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


PATCH_ID = '2.1.8-audit1'
PREFIX = 'openwebui-classroom-windows-x64/'


def build(output):
    source = Path(__file__).resolve().parents[1]
    output = Path(output).resolve()
    if output.exists() or output.with_suffix(output.suffix + '.sha256').exists():
        raise ValueError('patch output already exists; choose a new filename')
    selected = {}
    for folder in ('app', 'web', 'scripts'):
        root = source / folder
        if root in output.parents:
            raise ValueError('patch output cannot be inside its input tree')
        for path in root.rglob('*'):
            if path.is_symlink():
                raise ValueError('patch input cannot contain symlinks')
            if not path.is_file() or '__pycache__' in path.parts:
                continue
            if path.suffix not in {'.py', '.js', '.css', '.html', '.ps1', '.md', '.txt'}:
                continue
            selected[path.relative_to(source).as_posix()] = path
    for name in ('README.md', 'LICENSE', 'NOTICE', 'TEACHER_GUIDE_CN.md', 'IMPLEMENTATION_STATUS.md',
                 'PATCH_2.1.8_README.md', 'compatibility.json', 'docs/README.md',
                 'docs/CLASSROOM_AI_REQUIREMENTS.md', 'migrations/README.md'):
        selected[name] = source / name
    hashes = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in sorted(selected.items())}
    manifest = {'format_version': 1, 'patch_id': PATCH_ID, 'target_version': '2.1.8',
                'requires_open_webui': '0.11.2', 'classroom_schema_version': 5,
                'contains_runtime': False, 'contains_live_data': False, 'contains_credentials': False,
                'files': hashes}
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED) as archive:
        for name, path in sorted(selected.items()):
            archive.write(path, PREFIX + name)
        archive.writestr(PREFIX + 'patch-manifest-' + PATCH_ID + '.json', json.dumps(manifest, indent=2))
    with zipfile.ZipFile(output) as archive:
        if archive.testzip():
            raise ValueError('patch CRC verification failed')
        for name, expected in hashes.items():
            if hashlib.sha256(archive.read(PREFIX + name)).hexdigest() != expected:
                raise ValueError('patch content changed while packaging: ' + name)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + '.sha256').write_text(digest + '  ' + output.name + '\n', encoding='ascii')
    result = {'archive': str(output), 'patch_id': PATCH_ID, 'files': len(hashes), 'bytes': output.stat().st_size, 'sha256': digest}
    print(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    build(parser.parse_args().output)
