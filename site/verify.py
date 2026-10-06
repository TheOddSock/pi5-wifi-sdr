"""Check local static routes/assets, anchors, SVG accessibility and source copies."""
from __future__ import annotations
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

SITE = Path(__file__).resolve().parent
ROOT = SITE.parent
DIST = SITE / "dist"


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__(); self.urls = []; self.ids = set(); self.images = []
        self.feed(text)
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs: self.ids.add(attrs["id"])
        for key in ("href", "src"):
            if key in attrs: self.urls.append(attrs[key])
        if tag == "img": self.images.append(attrs)


def verify():
    problems = []; pages = {}
    for path in DIST.rglob("*.html"):
        pages[path.resolve()] = Page(path.read_text(encoding="utf-8"))
    links = 0
    for path, page in pages.items():
        for attrs in page.images:
            if not attrs.get("alt"): problems.append(f"Image without description: {path}")
        for url in page.urls:
            parts = urlsplit(url)
            if parts.scheme or parts.netloc: continue
            links += 1
            target = (path.parent / unquote(parts.path)).resolve() if parts.path else path
            try: target.relative_to(DIST)
            except ValueError:
                problems.append(f"Link escapes static root: {path.name}: {url}"); continue
            if not target.is_file():
                problems.append(f"Missing static link: {path.relative_to(DIST)}: {url}")
            elif parts.fragment and target in pages and unquote(parts.fragment) not in pages[target].ids:
                problems.append(f"Missing anchor: {path.relative_to(DIST)}: {url}")
    figures = []
    ns = {"svg": "http://www.w3.org/2000/svg"}
    for path in sorted((DIST / "assets").glob("*.svg")):
        tree = ET.parse(path).getroot()
        if tree.get("role") != "img" or tree.find("svg:title", ns) is None or tree.find("svg:desc", ns) is None:
            problems.append(f"SVG lacks accessible title/description: {path.name}")
        figures.append(path.name)
    if len(figures) != 4: problems.append("Expected four original diagrams")
    selected = ROOT / "evidence/known-signal-findings.json"
    mirrored = DIST / "reading/files/evidence/known-signal-findings.json"
    if selected.read_bytes() != mirrored.read_bytes(): problems.append("Known-source data differs from candidate")
    longrun = ROOT / "evidence/longrun-findings.json"
    if longrun.read_bytes() != (DIST / "reading/files/evidence/longrun-findings.json").read_bytes():
        problems.append("Selected longrun data differs from candidate")
    for subtree in ("device", "device-abi37"):
        for source in (ROOT / "src" / subtree).rglob("*"):
            if not source.is_file() or "__pycache__" in source.parts: continue
            target = DIST / "reading/files" / source.relative_to(ROOT)
            if source.suffix == ".md": target = target.with_suffix(".html")
            if not target.is_file(): problems.append("Missing source mirror: " + str(source.relative_to(ROOT)))
            elif source.suffix != ".md" and source.read_bytes() != target.read_bytes():
                problems.append("Source mirror differs: " + str(source.relative_to(ROOT)))
    metadata = json.loads((ROOT / "paper/metadata.json").read_text(encoding="utf-8"))
    if metadata["version"] not in (DIST / "index.html").read_text(encoding="utf-8"):
        problems.append("Overview version differs from candidate")
    pdf = DIST / "reading/report.pdf"
    if not pdf.is_file() or not pdf.read_bytes().startswith(b"%PDF-"):
        problems.append("Matching report PDF required")
    manifest = json.loads((SITE / "asset-manifest.json").read_text(encoding="utf-8"))
    actual = {p.relative_to(DIST).as_posix() for p in DIST.rglob("*") if p.is_file()}
    if actual != {r["path"] for r in manifest["files"]}: problems.append("Static asset set differs from its manifest")
    for row in manifest["files"]:
        p = DIST / row["path"]
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != row["sha256"]:
            problems.append("Static digest differs: " + row["path"])
    result = {"status": "fail" if problems else "pass", "html_pages": len(pages),
              "local_links": links, "diagrams": figures, "issues": problems, "publication": False}
    print(json.dumps(result, indent=2)); return bool(problems)


if __name__ == "__main__": raise SystemExit(verify())
