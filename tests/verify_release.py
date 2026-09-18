"""Extract only after checking archive paths; verify every manifest digest."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

parser=argparse.ArgumentParser()
parser.add_argument('archive')
parser.add_argument('destination')
args=parser.parse_args()
archive_path=Path(args.archive)
destination=Path(args.destination).resolve()
if destination.exists(): raise ValueError('use a new extraction directory')
prefix='openwebui-classroom-windows-x64/'
with zipfile.ZipFile(archive_path) as archive:
    names=archive.namelist()
    assert len(names)==len(set(n.casefold() for n in names))
    assert all(n.startswith(prefix) and '..' not in PurePosixPath(n).parts and '\\' not in n for n in names)
    manifest=json.loads(archive.read(prefix+'release-manifest.json'))
    assert set(names)=={prefix+n for n in manifest['files']}|{prefix+'release-manifest.json'}
    archive.extractall(destination)
root=destination/prefix
for name,digest in manifest['files'].items():
    with (root/name).open('rb') as handle:
        actual=hashlib.file_digest(handle,'sha256').hexdigest()
    assert actual==digest,name
assert not any((root/name).suffix in {'.db','.sqlite','.sqlite3'} or Path(name).name in {'.env','bridge.key','.webui_secret_key'} for name in manifest['files'])
print(json.dumps({'status':'RELEASE_EXTRACT_SHA256_OK','files':len(manifest['files']),'root':str(root)},ensure_ascii=False))
