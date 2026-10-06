"""Build a self-contained local static overview from the selected candidate.

No network, hardware, installation or publication. The source candidate remains
the authority; source pages are rendered for reading and links stay local.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import importlib.util
import json
import posixpath
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit

SITE = Path(__file__).resolve().parent
ROOT = SITE.parent
DIST = SITE / "dist"
EXCLUDED = {"release/manifest.json", "release/SHA256SUMS", "release/owner-approval.json", "pi5-receive-stream.pdf", "pi5-receive-stream-draft.pdf", "paper/release.html", "paper/review.html"}
sys.path.insert(0, str(ROOT / "tools"))
import build_report


def target_for(source: Path) -> Path:
    relative = source.relative_to(ROOT)
    if relative.as_posix() == "pi5-receive-stream.pdf": return DIST / "reading/report.pdf"
    if relative.as_posix() == "paper/release.html": return DIST / "reading/report.html"
    if relative.parts[:2] == ("site", "dist"):
        return DIST.joinpath(*relative.parts[2:])
    target = DIST / "reading/files" / relative
    return target.with_suffix(".html") if source.suffix == ".md" else target


def resolve_source(source: Path, url: str) -> Path:
    target = (source.parent / unquote(urlsplit(url).path)).resolve()
    target.relative_to(ROOT)  # never export an outside-workspace reference
    return target


def local_links(markup: str, source: Path, output: Path) -> str:
    def rewrite(match):
        url = html.unescape(match.group(2))
        parts = urlsplit(url)
        if parts.scheme or parts.netloc or not parts.path:
            return match.group(0)
        target = resolve_source(source, url)
        if not target.is_file():
            raise ValueError(f"Missing source link in {source.relative_to(ROOT)}: {url}")
        relative = posixpath.relpath(target_for(target).as_posix(), output.parent.as_posix())
        rewritten = urlunsplit(("", "", relative, parts.query, parts.fragment))
        return f'{match.group(1)}="{html.escape(rewritten, quote=True)}"'
    return re.sub(r'(href|src)="([^"]*)"', rewrite, markup)


def heading_id(text: str) -> str:
    text = re.sub(r"[`*]", "", text).lower()
    return re.sub(r"[^\w\- ]", "", text).replace(" ", "-")


def render_document(source: Path, output: Path):
    chunks = []
    for kind, value in build_report.blocks(source.read_text(encoding="utf-8")):
        if kind == "heading":
            level, title = value
            chunks.append(f'<h{level} id="{heading_id(title)}">{build_report.inline(title)}</h{level}>')
        elif kind == "image":
            chunks.append(f'<img alt="{html.escape(value[0], quote=True)}" src="{html.escape(value[1], quote=True)}">')
        elif kind == "table":
            rows = []
            for index, row in enumerate(value):
                tag = "th" if index == 0 else "td"
                rows.append("<tr>" + "".join(f"<{tag}>{build_report.inline(cell)}</{tag}>" for cell in row) + "</tr>")
            chunks.append('<div class="table-scroll"><table>' + "".join(rows) + "</table></div>")
        elif kind == "code":
            chunks.append("<pre><code>" + html.escape(value) + "</code></pre>")
        else:
            chunks.append("<p>" + ("• " if kind == "item" else "") + build_report.inline(value) + "</p>")
    body = local_links("\n".join(chunks), source, output)
    overview = posixpath.relpath((DIST / "index.html").as_posix(), output.parent.as_posix())
    css = posixpath.relpath((DIST / "reading.css").as_posix(), output.parent.as_posix())
    title = source.read_text(encoding="utf-8").splitlines()[0].lstrip("# ")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + html.escape(title) + '</title><link rel="stylesheet" href="' + css + '"></head><body><nav><a href="' + overview + '">Illustrated overview</a><span>Technical documentation</span></nav><main>' + body + '</main></body></html>\n', encoding="utf-8")


def source_files(manifest):
    # Do not mirror Git metadata, credentials, scratch files or unlisted content.
    admitted = {r["path"] for r in manifest["artifacts"]}
    admitted |= {"CITATION.cff", "release/approved-config.json"}
    return [p for p in sorted(ROOT.rglob("*")) if p.is_file() and
            "__pycache__" not in p.parts and SITE not in p.parents and
            p.relative_to(ROOT).parts[0] != ".git" and
            p.relative_to(ROOT).as_posix() in admitted - EXCLUDED]


def build(report_directory: Path | None):
    manifest = json.loads((ROOT / "release/manifest.json").read_text(encoding="utf-8"))
    if manifest.get("status") == "approved":
        raise ValueError("Preserve the approved candidate; create a new working draft first")
    sources = source_files(manifest)
    for source in sources:
        output = target_for(source)
        if source.suffix == ".md":
            render_document(source, output)
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, output)
    output = DIST / "reading/report.html"
    build_report.render_html(output)
    markup = local_links(output.read_text(encoding="utf-8"), ROOT / "paper/report.md", output)
    markup = re.sub(r"<style>.*?</style>", '<link rel="stylesheet" href="../reading.css">', markup, flags=re.S)
    markup = markup.replace("<body>", '<body><nav><a href="../index.html">Illustrated overview</a><a href="report.pdf">Download PDF</a></nav>')
    output.write_text(markup, encoding="utf-8")
    if report_directory:
        pdf = report_directory / "pi5-receive-stream.pdf"
        if not pdf.exists(): pdf = report_directory / "pi5-receive-stream-draft.pdf"
        shutil.copy2(pdf, DIST / "reading/report.pdf")
    version = json.loads((ROOT / "paper/metadata.json").read_text(encoding="utf-8"))["version"]
    index = DIST / "index.html"
    index.write_text(re.sub(r"(<span data-version>).*?(</span>)", rf"\g<1>{version}\g<2>", index.read_text(encoding="utf-8")), encoding="utf-8")
    generated = [{"path": p.relative_to(DIST).as_posix(), "bytes": p.stat().st_size,
                  "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                 for p in sorted(DIST.rglob("*")) if p.is_file()]
    (SITE / "asset-manifest.json").write_text(json.dumps({"version": version, "publication": False,
        "inputs": "Manifest-selected release files, no site recursion or approval/manifest copies",
        "files": generated}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"site_directory": str(DIST), "files": len(generated), "publication": False,
                      "pdf_included": (DIST / "reading/report.pdf").is_file()}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-directory", type=Path)
    build(parser.parse_args().report_directory)
