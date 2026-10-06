"""Reconstruct exact reviewed driver source from a reader-supplied kernel tree.

This copies local source and applies an explicit patch. It does not fetch, build,
install, unload modules or contact any device.
"""
import argparse,hashlib,json,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kernel-source',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();source=a.kernel_source.resolve();out=a.out.resolve()
    subtree=source/'drivers/net/wireless/broadcom/brcm80211'
    if subtree.is_dir():source=subtree
    if out.exists():raise ValueError('Preserve previous output; use a fresh directory')
    manifest=json.loads((ROOT/'expected-source.json').read_text())
    for r in manifest['upstream_base_files']:
        q=source/r['path']
        if not q.is_file() or q.is_symlink() or sha(q)!=r['sha256']:
            raise ValueError('Pinned pristine kernel source differs: '+r['path'])
    out.mkdir(parents=True)
    for r in manifest['upstream_base_files']:
        q=out/r['path'];q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source/r['path'],q)
    shutil.copyfile(ROOT/'base-Kbuild',out/'Kbuild')
    patch=ROOT/'twin6-linux.patch'
    subprocess.run(['git','apply','--check',str(patch)],cwd=out,check=True)
    subprocess.run(['git','apply',str(patch)],cwd=out,check=True)
    for q in (ROOT/'additions').rglob('*'):
        if q.is_file():
            dst=out/q.relative_to(ROOT/'additions');dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(q,dst)
    # Preserve historical byte identity after a portable LF-only logical patch.
    for name in manifest['exact_CRLF_files']:
        q=out/name;q.write_bytes(q.read_bytes().replace(b'\r\n',b'\n').replace(b'\n',b'\r\n'))
    actual={q.relative_to(out).as_posix():sha(q) for q in out.rglob('*') if q.is_file()}
    expected={r['path']:r['sha256'] for r in manifest['files']}
    if actual!=expected:raise ValueError('Reconstructed source does not match tested driver snapshot')
    print(json.dumps({'status':'exact_tested_driver_source_reconstructed','files':len(actual),
        'kernel_commit':manifest['kernel_commit'],'hardware_access':False,'module_compiled':False}))
if __name__=='__main__':main()
