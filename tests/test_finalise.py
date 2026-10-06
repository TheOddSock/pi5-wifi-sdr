"""Release preparation/approval regressions using fictional metadata only."""
import hashlib,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from finalise_release import prepare,approve,GENERATED,cff
from verify_release import canonical_sha256,content_sha256

class FinaliseTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name);self.source=self.base/'source';self.source.mkdir()
        files={'README.md':'# Synthetic only\n\nFictional fixture.\n','paper/report.md':'# Synthetic report\n\nTechnical report Draft synthetic.\n\n## Method\n\nNo experiment.\n',
               'paper/metadata.json':json.dumps({'title':'Synthetic report','version':'0.0.0-dev','status':'draft_not_public','approved_creators':[],'draft_date':'2000-01-01'}),
               'paper/implementation-appendix.md':'# Appendix Draft\n\nSynthetic text only.\n','LICENSES/test.txt':'Synthetic fixture licence text; grants no real project rights.\n',
               'THIRD_PARTY_NOTICES.md':'Synthetic fixture notice.\n','AI_ASSISTANCE.md':'Synthetic fixture.\n','CHANGELOG.md':'# History\n\nHistorical Draft 0.3.0-dev must remain unchanged.\n',
               'pi5-receive-stream.pdf':'Synthetic stand-in, not an actual PDF.\n','paper/release.html':'<p>Synthetic stand-in</p>\n'}
        for n,t in files.items():p=self.source/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(t)
        artifacts=[{'path':n,'bytes':(self.source/n).stat().st_size,'sha256':hashlib.sha256((self.source/n).read_bytes()).hexdigest(),'licence_scope':'pending_owner_review'} for n in sorted(files)]
        m={'schema_version':'1.0','status':'draft_for_owner_review','version':'0.0.0-dev','publication_approved':False,'artifacts':artifacts}
        p=self.source/'release/manifest.json';p.parent.mkdir();p.write_text(json.dumps(m))
        self.source_sha=hashlib.sha256(p.read_bytes()).hexdigest()
        paths=set(files)|GENERATED|{'LICENSE.md','CONTRIBUTIONS.md'}
        self.config={'schema_version':'1.0','source_candidate_manifest_sha256':self.source_sha,'version':'0.0.0-synthetic','title':'Synthetic only report',
          'creators':[{'name':'Synthetic Fixture Entity'}],'public_source_url':'https://example.invalid/synthetic-source','release_date':'2000-01-02','contributions':'Fictional fixture; no actual author or licence choice.',
          'licence_scopes':{'fixture':{'spdx_id':'LicenseRef-Synthetic-Fixture','text_path':'LICENSES/test.txt','notice_path':'THIRD_PARTY_NOTICES.md'}},
          'artifact_licence_scopes':{n:'fixture' for n in sorted(paths)},'approval_licence_scope':'fixture','synthetic_fixture':True}
        self.cfg=self.base/'config.json';self.cfg.write_text(json.dumps(self.config));self.output=self.base/'prepared'
    def tearDown(self):self.temp.cleanup()
    def test_prepare_preserves_source_and_needs_separate_approval(self):
        original=(self.source/'release/manifest.json').read_bytes();r=prepare(self.source,self.cfg,self.output,render=False)
        self.assertEqual((self.source/'release/manifest.json').read_bytes(),original)
        m=json.loads((self.output/'release/manifest.json').read_text());self.assertFalse(m['publication_approved']);self.assertEqual(r['reviewed_content_sha256'],content_sha256(m['artifacts']))
        self.assertFalse((self.output/'release/owner-approval.json').exists())
        self.assertIn('Synthetic Fixture Entity',(self.output/'CITATION.cff').read_text())
        self.assertNotIn('date-released:',(self.output/'CITATION.cff').read_text())
        self.assertEqual((self.output/'CHANGELOG.md').read_bytes(),(self.source/'CHANGELOG.md').read_bytes())
        with self.assertRaises(ValueError):approve(self.output,r['reviewed_content_sha256'])
        with self.assertRaises(ValueError):prepare(self.source,self.cfg,self.output,render=False)
    def test_changed_source_refused_before_export(self):
        (self.source/'README.md').write_text('changed')
        with self.assertRaisesRegex(ValueError,'Source artifact changed'):prepare(self.source,self.cfg,self.output,render=False)
        self.assertFalse(self.output.exists())
    def test_source_change_between_validation_and_copy_refused(self):
        import shutil
        real=shutil.copy2
        def changing(src,dst,*a,**kw):
            if Path(src)==self.source/'paper/report.md':Path(src).write_text('Unreviewed injected synthetic bytes')
            return real(src,dst,*a,**kw)
        with patch('finalise_release.shutil.copy2',side_effect=changing):
            with self.assertRaisesRegex(ValueError,'Source changed during copy'):prepare(self.source,self.cfg,self.output,render=False)
        self.assertFalse((self.output/'release/approved-config.json').exists())
    def test_source_manifest_is_parsed_and_hashed_from_one_read(self):
        real=Path.read_bytes;manifest=self.source/'release/manifest.json';reads=[]
        def tracked(path):
            if path==manifest:reads.append(path)
            return real(path)
        with patch.object(Path,'read_bytes',tracked):r=prepare(self.source,self.cfg,self.output,render=False)
        self.assertEqual(len(reads),1);self.assertEqual(r['source_candidate_manifest_sha256'],self.source_sha)
    def test_changed_prepared_content_cannot_be_approved(self):
        r=prepare(self.source,self.cfg,self.output,render=False);(self.output/'README.md').write_text('changed')
        with self.assertRaisesRegex(ValueError,'Prepared artifacts changed'):approve(self.output,r['reviewed_content_sha256'],True)
    def test_bad_configuration_or_scope_coverage_refused(self):
        self.config['creators']=[];self.cfg.write_text(json.dumps(self.config))
        with self.assertRaisesRegex(ValueError,'creators'):prepare(self.source,self.cfg,self.output,render=False)
        self.config['creators']=[{'name':'Synthetic Fixture Entity'}];self.config['artifact_licence_scopes'].pop('README.md');self.cfg.write_text(json.dumps(self.config))
        with self.assertRaisesRegex(ValueError,'exactly cover'):prepare(self.source,self.cfg,self.output,render=False)
    def test_canonical_config_helper_sources_not_exported(self):
        supplied=self.base/'inputs/text.txt';supplied.parent.mkdir();supplied.write_text((self.source/'LICENSES/test.txt').read_text())
        self.config['licence_scopes']['fixture']['text_source']='inputs/text.txt';self.cfg.write_text(json.dumps(self.config))
        r=prepare(self.source,self.cfg,self.output,render=False);c=json.loads((self.output/'release/approved-config.json').read_text())
        self.assertNotIn('text_source',c['licence_scopes']['fixture']);self.assertEqual(r['approved_config_sha256'],canonical_sha256(c))
    def test_synthetic_exact_approval_passes_strong_gate(self):
        r=prepare(self.source,self.cfg,self.output,render=False)
        with self.assertRaisesRegex(ValueError,'digest differs'):approve(self.output,'0'*64,True)
        result=approve(self.output,r['reviewed_content_sha256'],True)
        self.assertEqual(result['gate']['status'],'pass');self.assertFalse(result['publication'])
        record=json.loads((self.output/'release/owner-approval.json').read_text())
        self.assertTrue(record['synthetic_fixture']);self.assertEqual(record['reviewed_content_sha256'],r['reviewed_content_sha256'])
        with self.assertRaisesRegex(ValueError,'unapproved prepared'):approve(self.output,r['reviewed_content_sha256'],True)
    def test_cff_report_is_preferred_citation_without_posting_date(self):
        citation=json.loads(cff(self.config));self.assertEqual(citation['type'],'software');self.assertEqual(citation['preferred-citation']['type'],'report')
        self.assertNotIn('date-released',citation);self.assertEqual(citation['authors'][0],{'alias':'Synthetic Fixture Entity'})
        self.config['creators']=[{'name':'Synthetic Given Family','given-names':'Synthetic Given','family-names':'Family'}]
        self.assertEqual(json.loads(cff(self.config))['authors'][0],{'given-names':'Synthetic Given','family-names':'Family'})

    def test_licence_and_notice_cannot_target_any_rewritten_destination(self):
        from verify_release import RESERVED_LICENCE_PATHS
        for field in ['text_path','notice_path']:
            original=self.config['licence_scopes']['fixture'][field]
            for path in RESERVED_LICENCE_PATHS:
                with self.subTest(field=field,path=path):
                    self.config['licence_scopes']['fixture'][field]=path.upper()
                    self.cfg.write_text(json.dumps(self.config),encoding='utf-8')
                    with self.assertRaisesRegex(ValueError,'generated or rewritten'):
                        prepare(self.source,self.cfg,self.output,render=False)
                    self.assertFalse(self.output.exists())
            self.config['licence_scopes']['fixture'][field]=original

    def test_approval_exception_restores_exact_prepared_bytes_and_allows_retry(self):
        r=prepare(self.source,self.cfg,self.output,render=False)
        originals={n:(self.output/n).read_bytes() for n in ['release/manifest.json','release/SHA256SUMS']}
        with patch('finalise_release.verify',side_effect=RuntimeError('synthetic verifier interruption')):
            with self.assertRaisesRegex(RuntimeError,'synthetic verifier interruption'):
                approve(self.output,r['reviewed_content_sha256'],True)
        for n,raw in originals.items():self.assertEqual((self.output/n).read_bytes(),raw)
        self.assertFalse((self.output/'release/owner-approval.json').exists())
        failed=json.loads((self.base/'prepared.approval-failed.json').read_text(encoding='utf-8'))
        self.assertEqual(failed['status'],'fail')
        self.assertEqual(approve(self.output,r['reviewed_content_sha256'],True)['gate']['status'],'pass')

    def test_unreadable_markdown_refuses_approval_and_restores_prepared_state(self):
        bad=self.source/'auxiliary.md';bad.write_bytes(b'# Synthetic\n\x81\n')
        m=json.loads((self.source/'release/manifest.json').read_text(encoding='utf-8'))
        m['artifacts'].append({'path':'auxiliary.md','bytes':bad.stat().st_size,'sha256':hashlib.sha256(bad.read_bytes()).hexdigest(),'licence_scope':'pending_owner_review'})
        (self.source/'release/manifest.json').write_text(json.dumps(m),encoding='utf-8')
        self.config['source_candidate_manifest_sha256']=hashlib.sha256((self.source/'release/manifest.json').read_bytes()).hexdigest()
        self.config['artifact_licence_scopes']['auxiliary.md']='fixture'
        self.cfg.write_text(json.dumps(self.config),encoding='utf-8')
        r=prepare(self.source,self.cfg,self.output,render=False)
        original=(self.output/'release/manifest.json').read_bytes()
        with self.assertRaisesRegex(ValueError,'unreadable Markdown'):
            approve(self.output,r['reviewed_content_sha256'],True)
        self.assertEqual((self.output/'release/manifest.json').read_bytes(),original)
        self.assertFalse((self.output/'release/owner-approval.json').exists())

    def test_changed_manifest_title_is_refused_with_original_content_digest(self):
        r=prepare(self.source,self.cfg,self.output,render=False)
        p=self.output/'release/manifest.json';m=json.loads(p.read_text(encoding='utf-8'))
        m['title']='Unreviewed synthetic title';p.write_text(json.dumps(m),encoding='utf-8')
        original=p.read_bytes()
        with self.assertRaisesRegex(ValueError,'title'):
            approve(self.output,r['reviewed_content_sha256'],True)
        self.assertEqual(p.read_bytes(),original)
        self.assertFalse((self.output/'release/owner-approval.json').exists())

    def test_unicode_owner_metadata_survives_legacy_encoding_child(self):
        code=r'''
import json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from test_finalise import FinaliseTests,prepare,approve
assert sys.flags.utf8_mode==0
f=FinaliseTests();f.setUp()
try:
    name='Synthetic Jos\u00e9 Mu\u00f1oz';title='Synthetic Caf\u00e9 report'
    f.config['creators']=[{'name':name}];f.config['title']=title
    f.cfg.write_text(json.dumps(f.config,ensure_ascii=False),encoding='utf-8')
    r=prepare(f.source,f.cfg,f.output,render=False)
    for path in ['README.md','paper/report.md','paper/metadata.json','CITATION.cff']:
        text=(f.output/path).read_text(encoding='utf-8')
        assert name in text and title in text,path
    assert approve(f.output,r['reviewed_content_sha256'],True)['gate']['status']=='pass'
finally:f.tearDown()
'''
        env=dict(os.environ,PYTHONUTF8='0',PYTHONCOERCECLOCALE='0')
        result=subprocess.run([sys.executable,'-B','-X','utf8=0','-c',code,str(Path(__file__).parent)],capture_output=True,text=True,env=env)
        self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__':unittest.main()
