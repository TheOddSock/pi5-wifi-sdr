"""Check that the export validator catches tampering and unapproved release."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from verify_release import verify


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        (self.root/"release").mkdir();(self.root/"README.md").write_text("A synthetic review.\n")
        raw=(self.root/"README.md").read_bytes();h=hashlib.sha256(raw).hexdigest()
        self.manifest={"schema_version":"1.0","status":"draft_for_owner_review","approved_creators":[],
            "publication_approved":False,"release_blockers":["owner review pending"],
            "artifacts":[{"path":"README.md","bytes":len(raw),"sha256":h,"licence_scope":"pending_owner_review"}]}
        (self.root/"release/manifest.json").write_text(json.dumps(self.manifest))
        (self.root/"release/SHA256SUMS").write_text(h+"  README.md\n")

    def tearDown(self):self.temp.cleanup()

    def test_exact_draft_is_valid_but_publication_refused(self):
        self.assertEqual(verify(self.root)["status"],"pass")
        self.assertEqual(verify(self.root,True)["status"],"fail")

    def test_changed_bytes_and_extra_private_file_refused(self):
        (self.root/"README.md").write_text("Changed.\n")
        self.assertEqual(verify(self.root)["status"],"fail")
        (self.root/"private-notes.txt").write_text("Synthetic secret placeholder")
        self.assertIn("unlisted or absent candidate files",verify(self.root)["issues"])

    def test_checksum_list_and_broken_link_refused(self):
        (self.root/"release/SHA256SUMS").write_text("wrong\n")
        self.assertIn("SHA256SUMS differs from manifest",verify(self.root)["issues"])
        (self.root/"README.md").write_text("[missing](missing.md)\n")
        self.assertTrue(any("broken/external" in x for x in verify(self.root)["issues"]))

    def test_git_metadata_is_not_a_release_artifact_but_other_unlisted_files_are(self):
        (self.root/".git").mkdir();(self.root/".git/config").write_text("Synthetic Git metadata")
        self.assertEqual(verify(self.root)["status"],"pass")
        (self.root/"private.env").write_text("Synthetic unlisted data")
        self.assertEqual(verify(self.root)["status"],"fail")

    def test_path_traversal_refused(self):
        self.manifest["artifacts"][0]["path"]="../private-notes.txt"
        (self.root/"release/manifest.json").write_text(json.dumps(self.manifest))
        self.assertIn("unsafe or duplicate artifact path",verify(self.root)["issues"])

    def test_manifest_flags_and_blank_scope_do_not_approve_draft_metadata(self):
        # The review's exploit changed only these fields; the paper remained draft.
        (self.root/"paper").mkdir()
        (self.root/"paper/metadata.json").write_text(json.dumps({"version":"fixture",
            "status":"draft_not_public","approved_creators":[],"licence_status":"pending_owner_review"}))
        self.manifest.update({"status":"approved","approved_creators":[{"name":"Synthetic test only"}],
            "publication_approved":True,"release_blockers":[]})
        self.manifest["artifacts"][0]["licence_scope"]=""
        (self.root/"release/manifest.json").write_text(json.dumps(self.manifest))
        result=verify(self.root,True)
        self.assertFalse(result["publication_eligible"])
        self.assertIn("undeclared licence scope: README.md",result["issues"])
        self.assertIn("paper status is not approved for publication",result["issues"])
        self.assertIn("paper licence status unresolved",result["issues"])
        self.assertIn("exact owner approval record missing or invalid",result["issues"])

    def test_unknown_scope_is_not_a_licence_declaration(self):
        self.manifest["artifacts"][0]["licence_scope"]="made-up"
        (self.root/"release/manifest.json").write_text(json.dumps(self.manifest))
        self.assertIn("undeclared licence scope: README.md",verify(self.root,True)["issues"])

    def test_non_finite_manifest_and_missing_checksum_list_are_refused(self):
        (self.root/"release/manifest.json").write_text('{"artifacts": [], "version": NaN}')
        self.assertEqual(verify(self.root)["status"],"fail")
        (self.root/"release/manifest.json").write_text(json.dumps(self.manifest))
        (self.root/"release/SHA256SUMS").unlink()
        self.assertIn("SHA256SUMS differs from manifest",verify(self.root)["issues"])

    def test_array_metadata_is_a_refusal_result(self):
        (self.root/"paper").mkdir()
        (self.root/"paper/metadata.json").write_text("[]")
        result=verify(self.root,True)
        self.assertEqual(result["status"],"fail")
        self.assertIn("missing or invalid publication record: paper/metadata.json",result["issues"])

    def test_unreadable_markdown_returns_structured_failure(self):
        (self.root/'README.md').write_bytes(b'# Synthetic\n\x81\n')
        result=verify(self.root,True)
        self.assertEqual(result['status'],'fail')
        self.assertTrue(any('unreadable Markdown in README.md' in issue for issue in result['issues']))


if __name__=="__main__":unittest.main()
