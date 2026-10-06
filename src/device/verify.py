"""Check source-only review package identities and exclusions, without devices."""
import hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def main():
    m=json.loads((ROOT/'manifest.json').read_text());issues=[]
    expected={r['path']:r for r in m['files']}
    actual={p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    if actual!=set(expected)|{'manifest.json'}:issues.append('Unexpected/absent files')
    denied={'.bin','.ko','.elf','.o','.pcap','.pcapng','.gz','.tar','.zip'}
    privacy=re.compile(r'192\.168\.[0-9]+\.[0-9]+|C:\\Users\\')
    for n,r in expected.items():
        p=ROOT/n
        if p.is_symlink() or not p.is_file():issues.append('Missing/symlink: '+n);continue
        b=p.read_bytes()
        if len(b)!=r['bytes'] or hashlib.sha256(b).hexdigest()!=r['sha256']:issues.append('Digest differs: '+n)
        if p.suffix.lower() in denied:issues.append('Binary/archive excluded: '+n)
        if privacy.search(b.decode('utf-8',errors='replace')):issues.append('Private host detail: '+n)
    result={'status':'fail' if issues else 'pass','checked_files':len(expected),'issues':issues,
        'hardware_access':False,'new_source_licences_approved':False,'publication_eligible':False}
    print(json.dumps(result,indent=2));raise SystemExit(bool(issues))
if __name__=='__main__':main()
