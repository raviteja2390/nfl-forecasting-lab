"""Dated write-once checkpoint directories and verified fresh-directory restore."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path,PurePosixPath
import re
import shutil
import subprocess
import zipfile


def safe(name):
    p=PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or str(p)!=name or not p.parts:
        raise ValueError('Unsafe checkpoint path')
    if any(x in ('.git','.venv','__pycache__') or x.startswith('.env') for x in p.parts) or p.suffix in ('.key','.pem'):
        raise ValueError('Excluded private/runtime path')
    return name


def create(root,destination):
    root=root.resolve();destination=destination.resolve()
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{6}Z-checkpoint',destination.name): raise ValueError('Use YYYY-MM-DDTHHMMSSZ-checkpoint name')
    if destination.is_relative_to(root): raise ValueError('Checkpoint must be outside source checkout')
    names=set(subprocess.check_output(['git','ls-files','-z'],cwd=root).decode().split('\0'))-{''}
    # Runtime evidence omitted by normal Git still belongs in the checkpoint.
    for prefix in ('forecasting/data/feeds','forecasting/data/snapshots','forecasting/live'):
        for p in (root/prefix).rglob('*'):
            if p.is_file() and not any(x.startswith('.') or x=='__pycache__' for x in p.relative_to(root).parts):
                names.add(p.relative_to(root).as_posix())
    destination.mkdir(parents=True,exist_ok=False)
    files={}
    with zipfile.ZipFile(destination/'checkpoint.zip','x',compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(names):
            safe(name);p=root/name
            if p.is_symlink() or not p.resolve().is_relative_to(root): raise ValueError('Symlink prohibited')
            body=p.read_bytes();files[name]={'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}
            archive.writestr(name,body)
    record={'schemaVersion':1,'createdAt':datetime.now(timezone.utc).isoformat(),
            'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
            'archiveSha256':hashlib.sha256((destination/'checkpoint.zip').read_bytes()).hexdigest(),'files':files,
            'protection':'Exclusive new directory, archive creation and manifest; no overwrite or delete operation. Owner/admin can still remove these files.'}
    with (destination/'manifest.json').open('x') as f: json.dump(record,f,indent=2);f.write('\n')
    for p in destination.iterdir(): p.chmod(0o444)
    destination.chmod(0o555)
    return record


def restore(snapshot,destination):
    record=json.loads((snapshot/'manifest.json').read_text())
    packed=snapshot/'checkpoint.zip'
    if hashlib.sha256(packed.read_bytes()).hexdigest()!=record['archiveSha256']: raise ValueError('Archive checksum mismatch')
    # Verify every member before writing anything. Refuse an existing destination.
    with zipfile.ZipFile(packed) as archive:
        if len(archive.namelist())!=len(set(archive.namelist())) or set(archive.namelist())!=set(record['files']): raise ValueError('Manifest membership mismatch')
        for name in archive.namelist():
            safe(name);info=record['files'][name];body=archive.read(name)
            if len(body)!=info['bytes'] or hashlib.sha256(body).hexdigest()!=info['sha256']: raise ValueError('File checksum mismatch')
        destination.mkdir(parents=True,exist_ok=False)
        for name in archive.namelist():
            path=destination/name;path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('xb') as f:f.write(archive.read(name))
    return {'restoredFiles':len(record['files']),'commit':record['commit']}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=('create','restore'));p.add_argument('--source',type=Path,required=True);p.add_argument('--destination',type=Path,required=True)
    a=p.parse_args();r=(create if a.command=='create' else restore)(a.source,a.destination)
    print(json.dumps({k:v for k,v in r.items() if k!='files'}))
