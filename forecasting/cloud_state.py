"""Transfer checked, compressed research state to a dedicated private Git branch."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil

ROOT=Path(__file__).resolve().parent.parent
PREFIXES=('forecasting/data/feeds/','forecasting/data/snapshots/','forecasting/live/')
MAX_FILE_BYTES=30_000_000
MAX_COMPRESSED_BYTES=250_000_000


def safe_path(name):
    p=PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or str(p)!=name or not name.startswith(PREFIXES) or any(part.startswith('.') for part in p.parts):
        raise ValueError('Unsafe state path')
    return name


def mutable(name):
    return name.startswith('forecasting/live/reports/') or name in ('forecasting/live/operations/status.json','forecasting/live/operations/health.json')


def manifest(state):
    p=state/'manifest.json'
    if not p.exists(): raise ValueError('Cloud state manifest missing; never reset to an empty archive')
    value=json.loads(p.read_text())
    if value.get('schemaVersion')!=1 or not isinstance(value.get('files'),dict): raise ValueError('Invalid state manifest')
    return value


def checked_destination(root,name):
    destination=root/name
    if not destination.resolve().is_relative_to(root.resolve()): raise ValueError('State path escapes destination')
    if destination.is_symlink(): raise ValueError('State destination is a symlink')
    return destination


def restore(state,root=ROOT):
    index=manifest(state)
    for name,record in index['files'].items():
        safe_path(name)
        if type(record.get('bytes')) is not int or not 0<=record['bytes']<=MAX_FILE_BYTES: raise ValueError('Invalid state payload size')
        packed=checked_destination(state,'files/'+name+'.gz')
        with gzip.open(packed,'rb') as handle: body=handle.read(MAX_FILE_BYTES+1)
        if len(body)!=record['bytes'] or hashlib.sha256(body).hexdigest()!=record['sha256']: raise ValueError('Cloud state checksum mismatch: '+name)
        target=checked_destination(root,name)
        if target.exists() and not mutable(name) and target.read_bytes()!=body: raise ValueError('Immutable local evidence disagrees with cloud: '+name)
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(body)
    return {'restoredFiles':len(index['files'])}


def save(state,root=ROOT):
    state.mkdir(parents=True,exist_ok=True)
    previous=manifest(state)['files'] if (state/'manifest.json').exists() else {}
    files={}; packed_bytes=0
    for prefix in PREFIXES:
        for path in sorted((root/prefix).rglob('*')):
            if not path.is_file(): continue
            name=path.relative_to(root).as_posix()
            if any(part.startswith('.') or part=='__pycache__' for part in path.relative_to(root).parts): continue
            safe_path(name)
            if path.is_symlink(): raise ValueError('Symlinks cannot enter cloud state')
            body=path.read_bytes()
            if len(body)>MAX_FILE_BYTES: raise ValueError('Oversized state file')
            record={'sha256':hashlib.sha256(body).hexdigest(),'bytes':len(body)}
            if name in previous and not mutable(name) and record!=previous[name]: raise ValueError('Immutable state changed: '+name)
            files[name]=record
            target=checked_destination(state,'files/'+name+'.gz')
            if name not in previous or record!=previous[name]:
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(gzip.compress(body,compresslevel=6,mtime=0))
            packed_bytes+=target.stat().st_size
    if not set(previous).issubset(files): raise ValueError('Refusing to discard previously archived files')
    if packed_bytes>MAX_COMPRESSED_BYTES: raise ValueError('Cloud state exceeded 250 MB; migrate storage before continuing. Nothing may be pruned silently.')
    (state/'manifest.json').write_text(json.dumps({'schemaVersion':1,'files':files},sort_keys=True,indent=2)+'\n')
    for path in (root/'forecasting/live/reports').glob('*'):
        if path.is_file() and path.suffix in ('.md','.json'):
            target=state/'reports'/path.name; target.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(path,target)
    status=root/'forecasting/live/operations/status.json'
    if status.exists(): shutil.copyfile(status,state/'collector-status.json')
    (state/'README.md').write_text('# NFL persistent research state\n\nThis private branch is maintained by the cloud collector. Raw payloads, original forecasts and receipts are compressed individually and checked by manifest SHA-256 hashes. Do not edit or force-push this branch.\n\nReadable current outputs are in [reports](reports). See [collector-status.json](collector-status.json) for the last successful collection. Code and operating instructions are on the main branch.\n\nThis is versioned storage, not immutable or independent of GitHub. The 250 MB working-tree guard does not cap accumulated Git history; monitor repository size and migrate storage before it becomes large.\n')
    return {'files':len(files),'compressedBytes':packed_bytes}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=('save','restore')); p.add_argument('--state',type=Path,required=True); p.add_argument('--root',type=Path,default=ROOT)
    a=p.parse_args(); print(json.dumps((save if a.command=='save' else restore)(a.state,a.root)))
