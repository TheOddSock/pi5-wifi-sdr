"""Prepare and separately approve a fresh local release; never publish it.

Owner choices are inputs, never defaults. Source copying is manifest-allowlisted.
The approve command binds the exact prepared content after a separate review.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,re,shutil,subprocess,sys
from datetime import date
from pathlib import Path,PurePosixPath
from urllib.parse import urlsplit
from verify_release import canonical_sha256,content_sha256,verify,RESERVED_LICENCE_PATHS

EXCLUDED={'release/manifest.json','release/SHA256SUMS'}
OLD_RENDERS={'pi5-receive-stream-draft.pdf','paper/review.html'}
GENERATED={'CITATION.cff','release/approved-config.json','release/component-licences.csv','pi5-receive-stream.pdf','paper/release.html'}
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):
    return json.loads(p.read_text(encoding='utf-8'),parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))
def write(p,value):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
def safe(name):
    if not isinstance(name,str) or not name:return False
    p=PurePosixPath(name)
    return not p.is_absolute() and '..' not in p.parts and '\\' not in name and ':' not in name and name==p.as_posix()
def require(condition,message):
    if not condition:raise ValueError(message)
def config_check(c,source_sha):
    require(c.get('schema_version')=='1.0','Unsupported configuration schema')
    require(c.get('source_candidate_manifest_sha256')==source_sha,'Source manifest is not the approved input')
    require(isinstance(c.get('version'),str) and re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?',c['version']),'Invalid release version')
    require(isinstance(c.get('title'),str) and bool(c['title'].strip()),'Title required')
    creators=c.get('creators');require(isinstance(creators,list) and bool(creators),'Owner creators required')
    require(all(isinstance(x,dict) and isinstance(x.get('name'),str) and x['name'].strip() for x in creators),'Creator names must be explicit')
    for person in creators:
        if person.get('orcid'):
            require(isinstance(person['orcid'],str) and re.fullmatch(r'https://orcid\.org/[0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{3}[0-9X]',person['orcid']),'ORCID must be an explicit valid URI')
            require(person.get('kind')=='entity' or person.get('given-names') or person.get('family-names'),'A person with ORCID requires explicit structured citation names')
    u=urlsplit(c.get('public_source_url',''));require(u.scheme=='https' and bool(u.netloc) and not u.username and not u.password,'HTTPS public source URL required')
    require(date.fromisoformat(c.get('release_date','')).isoformat()==c['release_date'],'ISO release date required')
    require(isinstance(c.get('contributions'),str) and bool(c['contributions'].strip()),'Actual contribution statement required')
    scopes=c.get('licence_scopes');require(isinstance(scopes,dict) and bool(scopes),'Licence scope map required')
    for key,r in scopes.items():
        require(isinstance(key,str) and re.fullmatch(r'[A-Za-z0-9_.-]+',key),'Invalid scope ID')
        require(isinstance(r,dict) and isinstance(r.get('spdx_id'),str) and bool(r['spdx_id'].strip()),'Explicit licence identifier required')
        require(safe(r.get('text_path')) and safe(r.get('notice_path')),'Licence/notice paths must be local safe paths')
        require(all(r[n].casefold() not in RESERVED_LICENCE_PATHS for n in ['text_path','notice_path']),
                'Licence/notice destination is generated or rewritten')
        for n in ['text_source','notice_source']:
            if n in r:require(safe(r[n]),'External licence input must be relative to the config directory')
    mapping=c.get('artifact_licence_scopes');require(isinstance(mapping,dict),'Exact artifact scope map required')
    require(all(safe(n) and v in scopes for n,v in mapping.items()),'Invalid or undeclared artifact scope')
    require(c.get('approval_licence_scope') in scopes,'Approval record needs an explicit scope')
    require('owner_approval' not in c,'Approval is a separate exact-output step, not a config field')

def cff(c):
    # JSON is valid YAML1.2, avoiding a YAML emitter dependency and preserving
    # owner Unicode/quoting exactly. The bundled software has a preferred report
    # citation; CFF1.2 permits only software/dataset as the top-level type.
    authors=[]
    for person in c['creators']:
        if person.get('kind')=='entity':author={'name':person['name']}
        elif person.get('given-names') or person.get('family-names'):
            author={k:person[k] for k in ['given-names','family-names'] if person.get(k)}
        else:author={'alias':person['name']}
        for k in ['affiliation','orcid']:
            if person.get(k) and not (k=='affiliation' and person.get('kind')=='entity'):author[k]=person[k]
        authors.append(author)
    value={'cff-version':'1.2.0','message':'Please cite the technical report in preferred-citation and its exact version.',
           'title':c['title'],'type':'software','version':c['version'],'url':c['public_source_url'],'authors':authors,
           'preferred-citation':{'type':'report','title':c['title'],'version':c['version'],'url':c['public_source_url'],'authors':authors}}
    # No date-released while actual public availability has not been recorded.
    return json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n'


def rows_for(root,c):
    files={p.relative_to(root).as_posix():p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.relative_to(root).as_posix() not in EXCLUDED|{'release/owner-approval.json'}}
    require(set(files)==set(c['artifact_licence_scopes']),'Config artifact map must exactly cover final content (including generated files)')
    return [{'path':n,'bytes':p.stat().st_size,'sha256':digest(p),'licence_scope':c['artifact_licence_scopes'][n],'role':'approved_release_artifact'} for n,p in sorted(files.items())]
def save_manifest(root,m):
    write(root/'release/manifest.json',m)
    (root/'release/SHA256SUMS').write_text(''.join(r['sha256']+'  '+r['path']+'\n' for r in m['artifacts']),encoding='utf-8')

def template(source,output):
    require(not output.exists(),'Template output already exists')
    m=load(source/'release/manifest.json');metadata=load(source/'paper/metadata.json')
    paths=({r['path'] for r in m['artifacts']}-OLD_RENDERS)|GENERATED|{'LICENSE.md','CONTRIBUTIONS.md'}
    if (source/'site/build.py').is_file():
        paths |= {'site/dist/reading/files/CITATION.cff','site/dist/reading/files/release/approved-config.json'}
    c={'schema_version':'1.0','source_candidate_manifest_sha256':digest(source/'release/manifest.json'),'version':None,'title':metadata['title'],'creators':[],
       'contributions':None,'public_source_url':None,'release_date':None,'licence_scopes':{},'artifact_licence_scopes':{n:None for n in sorted(paths)},'approval_licence_scope':None}
    write(output,c);return {'status':'unfilled_owner_template','publication':False,'file':str(output),'owner_choices_selected':False}

def prepare(source,config_path,output,render=True):
    source=source.resolve();output=output.resolve();config_path=config_path.resolve()
    require(not output.exists(),'Output must be a fresh directory; existing drafts/snapshots are never replaced')
    require(not output.is_relative_to(source) and not source.is_relative_to(output),'Output must be isolated from the source candidate')
    manifest_path=source/'release/manifest.json';raw=manifest_path.read_bytes()
    m=json.loads(raw,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    c=load(config_path);source_sha=hashlib.sha256(raw).hexdigest();config_check(c,source_sha)
    entries={}
    for r in m['artifacts']:
        n=r['path'];require(safe(n) and n not in entries and n not in EXCLUDED,'Unsafe/duplicate source artifact')
        p=source/n;require(p.is_file() and not p.is_symlink() and p.stat().st_size==r['bytes'] and digest(p)==r['sha256'],'Source artifact changed: '+n);entries[n]=p
    require(m.get('publication_approved') is not True,'Use an unapproved preserved source snapshot for preparation')
    output.mkdir(parents=True)
    for n,p in entries.items():
        if n in OLD_RENDERS:continue
        dest=output/n;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
        declared=next(r for r in m['artifacts'] if r['path']==n)
        require(dest.stat().st_size==declared['bytes'] and digest(dest)==declared['sha256'],'Source changed during copy: '+n)
    for scope in c['licence_scopes'].values():
        for local,external in [('text_path','text_source'),('notice_path','notice_source')]:
            dest=output/scope[local]
            if external in scope:
                inp=config_path.parent/scope[external];require(inp.is_file() and not inp.is_symlink(),'Missing licence/notice input')
                require(not dest.exists() or dest.read_bytes()==inp.read_bytes(),'Conflicting licence/notice input')
                dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(inp,dest)
            require(dest.is_file() and bool(dest.read_text(encoding='utf-8').strip()),'Licence text/notice must be present and nonempty')
    # Acquisition helpers are private preparation inputs, not release metadata.
    c=dict(c);c['licence_scopes']={s:{k:v for k,v in r.items() if k not in ['text_source','notice_source']} for s,r in c['licence_scopes'].items()}
    metadata=load(output/'paper/metadata.json');metadata.update({'title':c['title'],'version':c['version'],'status':'approved_for_publication','approved_creators':c['creators'],'public_repository_url':c['public_source_url'],'release_date':c['release_date'],'licence_status':'approved','public_release_time_utc':None})
    write(output/'paper/metadata.json',metadata);write(output/'release/approved-config.json',c)
    (output/'CITATION.cff').write_text(cff(c),encoding='utf-8')
    names='; '.join(x['name'] for x in c['creators'])
    licence_table='| Scope | Licence identifier | Licence text | Notice |\n|---|---|---|---|\n'+''.join('| '+k+' | '+v['spdx_id']+' | ['+v['text_path']+']('+v['text_path']+') | ['+v['notice_path']+']('+v['notice_path']+') |\n' for k,v in c['licence_scopes'].items())
    (output/'LICENSE.md').write_text('# Licence scopes\n\nThe owner-supplied configuration selects the following component scopes. Existing third-party notices remain applicable. This does not license excluded manufacturer images or private recordings.\n\n'+licence_table+'\nExact file assignments are in [the component map](release/component-licences.csv).\n',encoding='utf-8')
    (output/'CONTRIBUTIONS.md').write_text('# Contributions\n\n'+c['contributions']+'\n\nAI assistance is described in [AI_ASSISTANCE.md](AI_ASSISTANCE.md); upstream authors remain acknowledged separately.\n',encoding='utf-8')
    # Metadata wording only; numerical findings and source implementation remain intact.
    report=output/'paper/report.md';t=report.read_text(encoding='utf-8');lines=t.splitlines();lines[0]='# '+c['title'];t='\n'.join(lines)+'\n'
    t=re.sub(r'Technical report[^\n]*','Technical report '+c['version']+'. Prepared '+c['release_date']+'. Creators: '+names+'. Original report and diagrams: CC BY 4.0; original code: GPL-2.0-or-later. Retained upstream terms apply separately.',t,count=1)
    t=t.replace('New project licences, public creators and final privacy/distribution review await owner decisions.','Owner-selected component licences and creators are recorded in the release manifest; the manufacturer inputs and private-controller boundary remain unchanged.')
    report.write_text(t,encoding='utf-8')
    readme=output/'README.md';t=readme.read_text(encoding='utf-8');t=re.sub(r'\*\*Local review candidate[^\n]*','**Prepared release '+c['version']+'. Actual public availability is not yet recorded.**',t,count=1);t=t.split('\n',1)[0]+'\n\nTechnical report: '+c['title']+'.\n\nAuthor: '+names+'. Prepared '+c['release_date']+'. [Source and evidence]('+c['public_source_url']+').\n\n'+t.split('\n',1)[1];readme.write_text(t,encoding='utf-8')
    # Change current presentation sentences only, never historic version claims
    # or the source package's provenance documents and nested hash manifest.
    replacements={
        "README.md":{
          "Author names, affiliations, licences, public repository URL, DOI and public release date await owner review.":"Approved creators, contribution statement, component licences and source URL are recorded in this release. Actual public availability and any DOI remain unrecorded.",
          "The source-only device recipe is included for owner review":"The source-only device recipe is included under the owner-selected component scopes"},
        "paper/report.md":{
          "The public human contribution record awaits owner review.":"The owner-supplied human contribution record is included in CONTRIBUTIONS.md."},
        "AI_ASSISTANCE.md":{
          "The human author list and contribution record require owner review.":"The owner-supplied creator list and contribution record are included in this release."},
        "paper/implementation-appendix.md":{"# Implementation appendix Draft":"# Implementation appendix"},
    }
    for name,changes in replacements.items():
        f=output/name
        if f.exists():
            text=f.read_text(encoding='utf-8')
            for old,new in changes.items():text=text.replace(old,new)
            f.write_text(text,encoding='utf-8')
    readme=output/'README.md'
    with (output/'release/component-licences.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(['path','licence_scope','spdx_id','text_path','notice_path'])
        for n,s in sorted(c['artifact_licence_scopes'].items()):v=c['licence_scopes'][s];w.writerow([n,s,v['spdx_id'],v['text_path'],v['notice_path']])
    if render:
        # Renderer executes from the isolated export, never from a mutable source.
        render_out=output.parent/(output.name+'.render')
        result=subprocess.run([sys.executable,'-B',str(output/'tools/build_report.py'),'--output-dir',str(render_out)],capture_output=True,text=True)
        require(result.returncode==0,'Report rendering failed: '+result.stderr)
        shutil.copy2(render_out/'pi5-receive-stream.pdf',output/'pi5-receive-stream.pdf');shutil.copy2(render_out/'release.html',output/'paper/release.html')
    if render and (output/'site/build.py').is_file():
        # The copied site must be rebuilt against final metadata and final PDF.
        write(output/'release/manifest.json',dict(m,status='prepared_for_owner_review'))
        result=subprocess.run([sys.executable,'-B',str(output/'site/build.py'),'--report-directory',str(render_out)],capture_output=True,text=True)
        require(result.returncode==0,'Site rendering failed: '+result.stderr)
        result=subprocess.run([sys.executable,'-B',str(output/'site/verify.py')],capture_output=True,text=True)
        require(result.returncode==0,'Site verification failed: '+result.stdout+result.stderr)
    artifacts=rows_for(output,c)
    m.update({'title':c['title'],'version':c['version'],'approved_creators':c['creators'],'public_repository_url':c['public_source_url'],'release_date':c['release_date'],'licence_scopes':c['licence_scopes'],'status':'prepared_for_owner_review','publication_approved':False,'public_release_time_utc':None,'source_candidate_manifest_sha256':source_sha,'approved_config_sha256':canonical_sha256(c),'artifacts':artifacts,'release_blockers':['Owner must approve the exact prepared artifact digest']})
    save_manifest(output,m)
    receipt={'status':'prepared_not_approved','publication':False,'source_candidate_manifest_sha256':source_sha,'approved_config_sha256':canonical_sha256(c),'reviewed_content_sha256':content_sha256(artifacts)}
    write(output.parent/(output.name+'.preparation.json'),receipt);return receipt

def approve(prepared,expected,owner_approved=False):
    require(owner_approved is True,'Explicit owner approval is required after reviewing prepared output')
    root=prepared.resolve();m=load(root/'release/manifest.json');c=load(root/'release/approved-config.json')
    require(m.get('status')=='prepared_for_owner_review' and m.get('publication_approved') is False,'Only an unapproved prepared export can be approved')
    require(canonical_sha256(c)==m.get('approved_config_sha256'),'Approved config changed')
    config_check(c,m['source_candidate_manifest_sha256'])
    rows=rows_for(root,c);require(rows==m['artifacts'],'Prepared artifacts changed since preparation')
    require(content_sha256(rows)==expected,'Expected exact-content digest differs')
    record={'schema_version':'1.0','reviewed_content_sha256':expected,'source_candidate_manifest_sha256':m['source_candidate_manifest_sha256'],'approved_config_sha256':m['approved_config_sha256'],'owner_approved':True,'scope':'exact prepared artifact set'}
    if c.get('synthetic_fixture') is True:record['synthetic_fixture']=True
    target=root/'release/owner-approval.json';require(not target.exists(),'Approval record already exists')
    # Preserve the exact prepared bytes, including their formatting. All writes
    # and verification belong to one exception-safe transition.
    original_manifest=(root/'release/manifest.json').read_bytes()
    original_sums=(root/'release/SHA256SUMS').read_bytes()
    result=None
    try:
        write(target,record)
        m['artifacts'].append({'path':'release/owner-approval.json','bytes':target.stat().st_size,'sha256':digest(target),'licence_scope':c['approval_licence_scope'],'role':'owner_approval_record'});m['artifacts'].sort(key=lambda r:r['path'])
        m.update({'status':'approved','publication_approved':True,'release_blockers':[]});save_manifest(root,m)
        result=verify(root,publish=True)
        if result['status']!='pass':
            raise ValueError('Publication gate rejected approval; prepared state restored: '+json.dumps(result['issues']))
    except BaseException as exc:
        (root/'release/manifest.json').write_bytes(original_manifest)
        (root/'release/SHA256SUMS').write_bytes(original_sums)
        target.unlink(missing_ok=True)
        failure=result if isinstance(result,dict) else {'status':'fail','issues':[type(exc).__name__+': '+str(exc)]}
        write(root.parent/(root.name+'.approval-failed.json'),failure)
        raise
    return {'status':'approved_local_export','publication':False,'reviewed_content_sha256':expected,'gate':result}

def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='command',required=True)
    prep=s.add_parser('prepare');prep.add_argument('--source',type=Path,required=True);prep.add_argument('--config',type=Path,required=True);prep.add_argument('--output',type=Path,required=True)
    a=s.add_parser('approve');a.add_argument('--prepared',type=Path,required=True);a.add_argument('--expected-content-sha256',required=True);a.add_argument('--owner-approved',action='store_true')
    t=s.add_parser('template');t.add_argument('--source',type=Path,required=True);t.add_argument('--output',type=Path,required=True)
    x=p.parse_args()
    try:
        if x.command=='prepare':r=prepare(x.source,x.config,x.output)
        elif x.command=='template':r=template(x.source,x.output)
        else:r=approve(x.prepared,x.expected_content_sha256,x.owner_approved)
    except (ValueError,KeyError,OSError,json.JSONDecodeError) as e:print(json.dumps({'status':'fail','publication':False,'error':str(e)}));raise SystemExit(1)
    print(json.dumps(r,indent=2))
if __name__=='__main__':main()
