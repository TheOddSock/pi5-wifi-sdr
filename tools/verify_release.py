"""Validate candidate files and hashes; --publish enforces final release fields."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
from datetime import date
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {"release/manifest.json", "release/SHA256SUMS"}
APPROVAL_PATH = "release/owner-approval.json"
# These destinations are generated, rewritten or removed during preparation.
# Supplied legal text must survive at its own stable destination.
RESERVED_LICENCE_PATHS = frozenset(name.casefold() for name in (
    "release/manifest.json", "release/SHA256SUMS", APPROVAL_PATH,
    "CITATION.cff", "release/approved-config.json", "release/component-licences.csv",
    "pi5-receive-stream.pdf", "paper/release.html", "pi5-receive-stream-draft.pdf",
    "paper/review.html", "LICENSE.md", "CONTRIBUTIONS.md", "paper/metadata.json",
    "README.md", "paper/report.md", "AI_ASSISTANCE.md", "paper/implementation-appendix.md",
))


def canonical_sha256(value):
    """Hash strict canonical JSON; this is an identity, not proof of permission."""
    data = json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def content_sha256(artifacts):
    """Bind the exact files/scopes awaiting approval, excluding the approval itself."""
    rows = [{k: r[k] for k in ("path", "bytes", "sha256", "licence_scope")}
            for r in artifacts if r["path"] != APPROVAL_PATH]
    return canonical_sha256(sorted(rows, key=lambda r: r["path"]))


def read_json(path):
    def invalid(value):
        raise ValueError("non-finite JSON constant: " + value)
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=invalid)


def safe_name(name):
    if not isinstance(name, str) or not name or ":" in name or "\\" in name:
        return False
    p = PurePosixPath(name)
    return not p.is_absolute() and ".." not in p.parts and p.as_posix() == name


def publication_issues(root, manifest, listed):
    """Check internally consistent owner records; cannot certify legal suitability."""
    issues = []
    def require(condition, message):
        if not condition: issues.append(message)
    def load(name):
        try:
            record = read_json(root / name)
            if not isinstance(record, dict):
                raise ValueError("publication record must be an object")
            return record
        except (OSError, ValueError, TypeError):
            issues.append("missing or invalid publication record: " + name)
            return {}
    require(manifest.get("status") == "approved", "status must be approved")
    require(manifest.get("publication_approved") is True, "owner publication approval missing")
    blockers = manifest.get("release_blockers")
    require(isinstance(blockers, list) and not blockers, "release blockers remain or are invalid")
    creators = manifest.get("approved_creators")
    require(isinstance(creators, list) and bool(creators) and all(
        isinstance(c, dict) and isinstance(c.get("name"), str) and bool(c["name"].strip())
        for c in creators), "approved creators missing or invalid")
    metadata = load("paper/metadata.json")
    require(metadata.get("status") == "approved_for_publication", "paper status is not approved for publication")
    require(metadata.get("licence_status") == "approved", "paper licence status unresolved")
    for field in ("title", "version", "approved_creators", "public_repository_url", "release_date"):
        require(metadata.get(field) == manifest.get(field) and metadata.get(field) not in (None, "", []),
                "paper/manifest mismatch or missing: " + field)
    try:
        release_date = manifest.get("release_date")
        valid_date = isinstance(release_date, str) and date.fromisoformat(release_date).isoformat() == release_date
    except ValueError:
        valid_date = False
    require(valid_date, "release metadata date missing or invalid")
    source_url = manifest.get("public_repository_url")
    url = urlsplit(source_url if isinstance(source_url, str) else "")
    require(url.scheme == "https" and bool(url.netloc) and not url.username and not url.password,
            "public evidence/source HTTPS URL missing or invalid")
    require(metadata.get("public_release_time_utc") == manifest.get("public_release_time_utc"),
            "actual publication time mismatch")
    scopes = manifest.get("licence_scopes")
    if not isinstance(scopes, dict) or not scopes:
        issues.append("declared licence scopes missing or invalid")
        scopes = {}
    for scope_id, scope in scopes.items():
        require(isinstance(scope_id, str) and bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", scope_id))
                and scope_id != "pending_owner_review", "invalid licence scope ID")
        if not isinstance(scope, dict):
            issues.append("invalid licence scope declaration: " + str(scope_id)); continue
        require(isinstance(scope.get("spdx_id"), str) and bool(scope["spdx_id"].strip())
                and "pending" not in scope["spdx_id"].lower(), "licence identifier unresolved: " + str(scope_id))
        for field in ("text_path", "notice_path"):
            name = scope.get(field)
            require(safe_name(name) and name in listed, "unbound licence text/notice: " + str(scope_id))
            require(not isinstance(name, str) or name.casefold() not in RESERVED_LICENCE_PATHS,
                    "licence text/notice uses a rewritten destination: " + str(scope_id))
            if safe_name(name) and name in listed:
                p = root / name
                require(p.is_file() and not p.is_symlink() and bool(p.read_text(encoding="utf-8").strip()),
                        "empty licence text/notice: " + str(scope_id))
    for row in manifest["artifacts"]:
        require(row.get("licence_scope") in scopes, "undeclared licence scope: " + row["path"])
    require("LICENSE.md" in listed and "THIRD_PARTY_NOTICES.md" in listed,
            "licence scope map and third-party notices must be bound")
    require("release/component-licences.csv" in listed and "CITATION.cff" in listed,
            "component licence mapping and citation metadata must be bound")
    config = load("release/approved-config.json")
    approval = load(APPROVAL_PATH)
    require("release/approved-config.json" in listed and APPROVAL_PATH in listed,
            "owner config and approval must be hash-bound artifacts")
    config_sha = canonical_sha256(config)
    require(manifest.get("approved_config_sha256") == config_sha == approval.get("approved_config_sha256"),
            "approved config identity mismatch")
    source_sha = manifest.get("source_candidate_manifest_sha256")
    require(isinstance(source_sha, str) and bool(re.fullmatch(r"[0-9a-f]{64}", source_sha))
            and source_sha == config.get("source_candidate_manifest_sha256") == approval.get("source_candidate_manifest_sha256"),
            "reviewed source candidate identity mismatch")
    require(approval.get("schema_version") == "1.0" and approval.get("owner_approved") is True
            and approval.get("scope") == "exact prepared artifact set", "exact owner approval record missing or invalid")
    require(approval.get("reviewed_content_sha256") == content_sha256(manifest["artifacts"]),
            "owner approval does not bind exact artifact bytes and licence scopes")
    for field, mfield in (("title", "title"), ("version", "version"), ("creators", "approved_creators"),
                          ("public_source_url", "public_repository_url"), ("release_date", "release_date"),
                          ("licence_scopes", "licence_scopes")):
        require(config.get(field) == manifest.get(mfield), "approved config/manifest mismatch: " + field)
    require(config.get("title") == metadata.get("title"), "approved config/paper title mismatch")
    mapping = config.get("artifact_licence_scopes", {})
    expected_mapping = {r["path"]: r["licence_scope"] for r in manifest["artifacts"] if r["path"] != APPROVAL_PATH}
    require(mapping == expected_mapping, "approved component licence map differs from exact artifacts")
    table = root / "release/component-licences.csv"
    if table.is_file():
        with table.open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        table_mapping = {r.get("path"): r.get("licence_scope") for r in rows}
        require(len(table_mapping) == len(rows) and table_mapping == expected_mapping,
                "component licence CSV differs from approved artifact map")
        for r in rows:
            declared = scopes.get(r.get("licence_scope"), {})
            require(all(r.get(k) == declared.get(k) for k in ("spdx_id", "text_path", "notice_path")),
                    "component licence CSV declaration mismatch: " + str(r.get("path")))
    approval_row = next((r for r in manifest["artifacts"] if r["path"] == APPROVAL_PATH), {})
    require(config.get("approval_licence_scope") == approval_row.get("licence_scope") and bool(approval_row),
            "approval record licence scope mismatch")
    return issues


def verify(root=ROOT, publish=False):
    root = Path(root)
    try:
        manifest = read_json(root / "release/manifest.json")
        if not isinstance(manifest, dict) or not isinstance(manifest.get("artifacts"), list):
            raise ValueError("manifest/artifacts missing")
    except (OSError, ValueError, TypeError) as exc:
        return {"status":"fail", "mode":"publication" if publish else "draft", "checked_files":0,
                "issues":["invalid manifest: " + str(exc)], "publication_eligible":False}
    issues = []
    if manifest.get("schema_version") != "1.0": issues.append("unsupported manifest schema")
    listed = set()
    for row in manifest["artifacts"]:
        if not isinstance(row, dict) or not all(k in row for k in ("path", "bytes", "sha256", "licence_scope")):
            issues.append("invalid artifact record"); continue
        name = row["path"]
        if not safe_name(name) or name in listed:
            issues.append("unsafe or duplicate artifact path"); continue
        listed.add(name); path = root / name
        if path.is_symlink() or not path.is_file():
            issues.append(f"missing or symlink artifact: {name}"); continue
        if path.stat().st_size != row["bytes"] or hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
            issues.append(f"size/hash mismatch: {name}")
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*")
              if p.is_file() and "__pycache__" not in p.parts and p.relative_to(root).parts[0] != ".git"}
    if actual != listed | EXCLUDED: issues.append("unlisted or absent candidate files")
    expected_sums = "".join(str(row.get("sha256", ""))+"  "+str(row.get("path", ""))+"\n"
                            for row in manifest["artifacts"] if isinstance(row, dict))
    try:
        sums = (root/"release/SHA256SUMS").read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        sums = None
    if sums != expected_sums:
        issues.append("SHA256SUMS differs from manifest")
    if any(p.is_symlink() for p in root.rglob("*") if "__pycache__" not in p.parts and p.relative_to(root).parts[0] != ".git"):
        issues.append("candidate contains a symlink")
    for p in root.rglob("*.md"):
        if p.relative_to(root).parts[0] == ".git": continue
        try:
            text = re.sub(r"```.*?```", "", p.read_text(encoding="utf-8"), flags=re.S)
        except (OSError, UnicodeError) as exc:
            issues.append(f"unreadable Markdown in {p.relative_to(root)}: {type(exc).__name__}")
            continue
        for link in re.findall(r"!?\[[^\]]*\]\(([^\s)]+)\)", text):
            if link.startswith(("#", "https://", "http://", "mailto:")): continue
            target = (p.parent / link.split("#")[0]).resolve()
            if not target.is_relative_to(root.resolve()) or not target.exists():
                issues.append(f"broken/external local link in {p.relative_to(root)}")
    if publish:
        if not any(x in ("invalid artifact record", "unsafe or duplicate artifact path") for x in issues):
            try:
                issues.extend(publication_issues(root, manifest, listed))
            except (OSError, ValueError, TypeError, KeyError, UnicodeError) as exc:
                issues.append("invalid publication records: " + str(exc))
    return {"status": "fail" if issues else "pass", "mode": "publication" if publish else "draft",
            "checked_files": len(listed), "issues": issues,
            "publication_eligible": not issues and publish}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__); p.add_argument("--publish", action="store_true")
    args = p.parse_args(); result = verify(publish=args.publish)
    print(json.dumps(result, indent=2)); raise SystemExit(result["status"] != "pass")
