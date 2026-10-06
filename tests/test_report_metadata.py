"""Renderer presentation tests with fictional metadata, when PDF deps exist."""
import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
try:
    import build_report
    from pypdf import PdfReader
except ImportError:
    build_report=None

@unittest.skipIf(build_report is None,'Optional ReportLab/pypdf renderer dependencies unavailable')
class ReportMetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);(self.root/'paper').mkdir()
        (self.root/'paper/report.md').write_text('# Synthetic metadata test\n\nNo research or release approval.\n')
        (self.root/'paper/implementation-appendix.md').write_text('# Appendix\n\nSynthetic appendix.\n')
        self.meta={'title':'Synthetic & metadata test','version':'0.0.0-synthetic','draft_date':'2000-01-01','status':'draft_not_public','approved_creators':[]}
        self.context=patch.object(build_report,'ROOT',self.root);self.context.start()
    def tearDown(self):self.context.stop();self.temp.cleanup()
    def save(self):(self.root/'paper/metadata.json').write_text(json.dumps(self.meta))
    def test_prepared_presentation_does_not_assert_approval(self):
        self.meta.update(status='prepared_not_published',prepared_date='2000-01-02');self.save()
        metadata,approved=build_report.publication_metadata()
        self.assertFalse(approved)
        label=build_report.publication_label(metadata,approved)
        self.assertIn('Version 0.0.0-synthetic',label)
        self.assertNotIn('Approved',label);self.assertNotIn('Draft',label)

    def test_site_exports_only_admitted_sources(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('site_builder',Path(__file__).resolve().parents[1]/'site/build.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        (self.root/'.git').mkdir();(self.root/'.git/config').write_text('Synthetic Git metadata')
        (self.root/'private.env').write_text('Synthetic unlisted content')
        (self.root/'README.md').write_text('Allowed documentation')
        with patch.object(module,'ROOT',self.root),patch.object(module,'SITE',self.root/'site'):
            names=[p.relative_to(self.root).as_posix() for p in module.source_files({'artifacts':[{'path':'README.md'}]})]
        self.assertEqual(names,['README.md'])

    def test_draft_keeps_unpublished_pending_labels(self):
        self.save();build_report.render_html(self.root/'draft.html');t=(self.root/'draft.html').read_text()
        self.assertIn('Draft 0.0.0-synthetic',t);self.assertIn('Unpublished',t);self.assertIn('Creator metadata and licence decisions await owner review',t)
    def test_approved_pdf_html_have_owner_metadata_and_source(self):
        self.meta.update({'status':'approved_for_publication','approved_creators':[{'name':'Synthetic Fixture Entity'}],'release_date':'2000-01-02','licence_status':'approved','public_repository_url':'https://example.invalid/fixture','public_release_time_utc':None});self.save()
        build_report.render_pdf(self.root/'approved.pdf');build_report.render_html(self.root/'approved.html')
        pdf=PdfReader(self.root/'approved.pdf');t='\n'.join(p.extract_text() for p in pdf.pages)
        self.assertEqual(pdf.metadata.author,'Synthetic Fixture Entity');self.assertIn('Synthetic Fixture Entity',t);self.assertIn('Release 0.0.0-synthetic',t);self.assertNotIn('Creator metadata pending',t)
        urls=[a.get_object().get('/A',{}).get('/URI') for p in pdf.pages for a in p.get('/Annots',[])]
        self.assertIn('https://example.invalid/fixture',urls)
        html=(self.root/'approved.html').read_text();self.assertIn('Synthetic &amp; metadata test',html);self.assertIn('https://example.invalid/fixture',html);self.assertIn('Release 0.0.0-synthetic | Prepared 2000-01-02',html);self.assertNotIn('Approved; publication not recorded',html)
    def test_approved_missing_source_or_creators_refused(self):
        self.meta['status']='approved_for_publication';self.save()
        with self.assertRaises(ValueError):build_report.publication_metadata()

    def test_utf8_metadata_is_decoded_explicitly(self):
        self.meta.update({'title':'Synthetic Caf\u00e9','status':'approved_for_publication',
            'approved_creators':[{'name':'Synthetic Jos\u00e9 Mu\u00f1oz'}],
            'release_date':'2000-01-02','licence_status':'approved',
            'public_repository_url':'https://example.invalid/fixture'})
        (self.root/'paper/metadata.json').write_text(json.dumps(self.meta,ensure_ascii=False),encoding='utf-8')
        metadata,approved=build_report.publication_metadata()
        self.assertTrue(approved);self.assertEqual(metadata,self.meta)

    def test_selected_licences_are_visible_without_approving_the_draft(self):
        self.meta.update(licence_status='selected_by_owner',report_license='CC-BY-4.0',
                         original_code_license='GPL-2.0-or-later');self.save()
        build_report.render_pdf(self.root/'selected.pdf');build_report.render_html(self.root/'selected.html')
        pdf=PdfReader(self.root/'selected.pdf')
        text='\n'.join(p.extract_text() for p in pdf.pages)
        html=(self.root/'selected.html').read_text(encoding='utf-8')
        for content in (text,html):
            self.assertIn('CC-BY-4.0',content);self.assertIn('GPL-2.0-or-later',content)
            self.assertIn('Unpublished',content);self.assertIn('Creator metadata awaits owner review',content)
            self.assertNotIn('licence decisions await owner review',content)
        self.assertEqual(self.meta['approved_creators'],[])

if __name__=='__main__':unittest.main()
