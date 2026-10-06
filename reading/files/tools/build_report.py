"""Render the Markdown report and appendix to a searchable PDF and HTML.

Requires ReportLab; offline verification tools do not require this dependency.
Use a new output directory for every review build.
"""
from __future__ import annotations
import argparse
import base64
import html
import json
import re
import textwrap
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.utils import simpleSplit
from reportlab.platypus import Image, SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Preformatted, KeepTogether
from reportlab.lib.pagesizes import A4
from make_figures import FIGURES

ROOT=Path(__file__).resolve().parents[1]


def blocks(source):
    lines=source.splitlines(); i=0
    while i<len(lines):
        line=lines[i].strip()
        if not line:i+=1;continue
        if line.startswith("```"):
            code=[];i+=1
            while i<len(lines) and not lines[i].startswith("```"):code.append(lines[i]);i+=1
            yield "code","\n".join(code);i+=1;continue
        heading=re.match(r"^(#{1,6})\s+(.+)$",line)
        if heading:yield "heading",(len(heading[1]),heading[2]);i+=1;continue
        pic=re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)",line)
        if pic:yield "image",(pic[1],pic[2]);i+=1;continue
        if line.startswith("|") and i+1<len(lines) and re.match(r"^\|[\s:|-]+\|$",lines[i+1].strip()):
            rows=[[s.strip() for s in line.strip("|").split("|")]];i+=2
            while i<len(lines) and lines[i].strip().startswith("|"):
                rows.append([s.strip() for s in lines[i].strip().strip("|").split("|")]);i+=1
            yield "table",rows;continue
        bullet=re.match(r"^(?:[-*]\s+|\d+\.\s+)(.*)$",line)
        if bullet:yield "item",bullet[1];i+=1;continue
        para=[line];i+=1
        while i<len(lines) and lines[i].strip() and not re.match(r"^(?:#|\||```|!\[|[-*]\s|\d+\.\s)",lines[i].strip()):
            para.append(lines[i].strip());i+=1
        yield "paragraph"," ".join(para)


def inline(value,pdf=False):
    # Source text is trusted candidate content, but HTML and attributes are escaped.
    token=r"(\[[^\]]+\]\([^)]+\)|`[^`]+`|\*\*[^*]+\*\*)"
    chunks=[]
    for part in re.split(token,value):
        m=re.fullmatch(r"\[([^\]]+)\]\(([^)]+)\)",part)
        if m:
            label,url=m.groups();safe=url.startswith(("https://","http://","#"))
            if pdf and not safe:chunks.append(html.escape(label));continue
            attr="href";chunks.append(f'<a {attr}="{html.escape(url,quote=True)}">{html.escape(label)}</a>')
        elif part.startswith("`") and part.endswith("`"):
            body=html.escape(part[1:-1]);chunks.append(f'<font name="Courier">{body}</font>' if pdf else f"<code>{body}</code>")
        elif part.startswith("**") and part.endswith("**"):chunks.append("<b>"+html.escape(part[2:-2])+"</b>")
        else:chunks.append(html.escape(part))
    return "".join(chunks)


def styles():
    s=getSampleStyleSheet()
    s.add(ParagraphStyle(name="ReportBody",fontName="Helvetica",fontSize=9.5,leading=13.4,spaceAfter=7,textColor=colors.HexColor("#243746"),splitLongWords=1,allowWidows=0,allowOrphans=0))
    s.add(ParagraphStyle(name="ReportTitle",parent=s["ReportBody"],fontSize=21,leading=26,spaceAfter=15,textColor=colors.HexColor("#176080"),keepWithNext=True))
    s.add(ParagraphStyle(name="ReportH2",parent=s["ReportBody"],fontSize=13,leading=17,spaceBefore=12,spaceAfter=7,textColor=colors.HexColor("#176080"),keepWithNext=True))
    s.add(ParagraphStyle(name="ReportH3",parent=s["ReportBody"],fontSize=10.5,leading=14,spaceBefore=9,spaceAfter=5,keepWithNext=True))
    s.add(ParagraphStyle(name="ReportCell",parent=s["ReportBody"],fontSize=8,leading=10.3,spaceAfter=0))
    s.add(ParagraphStyle(name="ReportCode",fontName="Courier",fontSize=7.1,leading=9.2,spaceAfter=8))
    s.add(ParagraphStyle(name="ReportItem",parent=s["ReportBody"],leftIndent=11,firstLineIndent=-7,spaceAfter=4))
    return s


def make_table(rows,style,width):
    count=len(rows[0]);cols=[width/count]*count
    # Evidence tables are easier to scan with more space for textual columns.
    if count==3:cols=[width*.29,width*.36,width*.35]
    if count==2:cols=[width*.27,width*.73]
    data=[[Paragraph(inline(cell,True),style["ReportCell"]) for cell in row] for row in rows]
    t=Table(data,colWidths=cols,repeatRows=1,hAlign="LEFT")
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#e7f1f5")),
                          ("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),6),
                          ("RIGHTPADDING",(0,0),(-1,-1),6),("TOPPADDING",(0,0),(-1,-1),5),
                          ("BOTTOMPADDING",(0,0),(-1,-1),5),("LINEBELOW",(0,0),(-1,0),.6,colors.HexColor("#9ab6c3")),
                          ("LINEBELOW",(0,1),(-1,-1),.3,colors.HexColor("#d8e4e9"))]))
    return t


def publication_metadata():
    metadata=json.loads((ROOT/"paper/metadata.json").read_text(encoding="utf-8"))
    approved=metadata.get("status")=="approved_for_publication"
    if approved:
        creators=metadata.get("approved_creators")
        if not isinstance(creators,list) or not creators or any(not isinstance(c,dict) or not c.get("name","").strip() for c in creators):
            raise ValueError("Approved report requires creator dictionaries with names")
        url=metadata.get("public_repository_url","")
        if not isinstance(url,str) or not url.startswith("https://"):
            raise ValueError("Approved report requires an explicit HTTPS public source URL")
        if not metadata.get("release_date") or metadata.get("licence_status")!="approved":
            raise ValueError("Approved report requires approved licence status and release date")
    return metadata,approved


def publication_label(metadata,approved):
    if metadata.get("status")=="prepared_not_published":
        return "Version "+metadata["version"]+" | Prepared "+metadata["prepared_date"]
    if approved:
        return "Release "+metadata["version"]+" | Prepared "+metadata["release_date"]
    return "Draft "+metadata["version"]+" | "+metadata["draft_date"]+" | Unpublished"


def publication_summary(metadata,approved):
    if metadata.get("status")=="prepared_not_published":
        return "Report and diagrams: CC BY 4.0. Original code: GPL-2.0-or-later."
    if not approved:
        if metadata.get('licence_status')=='selected_by_owner':
            return 'Creator metadata awaits owner review. Selected licences: '+metadata['report_license']+' (report); '+metadata['original_code_license']+' (original code).'
        return "Creator metadata and licence decisions await owner review."
    names="; ".join(c["name"] for c in metadata["approved_creators"])
    return "Author: "+names+". Source and evidence: [project repository]("+metadata["public_repository_url"]+"). Report and diagrams: CC BY 4.0; original code: GPL-2.0-or-later. Retained upstream terms apply separately."


def footer(canvas,doc):
    canvas.saveState();w,h=A4;canvas.setStrokeColor(colors.HexColor("#c8d7de"));canvas.line(47,40,w-47,40)
    canvas.setFillColor(colors.HexColor("#677784"));canvas.setFont("Helvetica",7)
    metadata,approved=publication_metadata()
    label="BCM43455 receive stream | "+publication_label(metadata,approved)
    canvas.drawString(47,28,label)
    canvas.drawRightString(w-47,28,str(doc.page));canvas.restoreState()


def render_pdf(path):
    s=styles();story=[];width=A4[0]-94
    metadata,approved=publication_metadata()
    for doc_index,name in enumerate(["report.md","implementation-appendix.md"]):
        if doc_index:story.append(PageBreak())
        parsed=list(blocks((ROOT/"paper"/name).read_text(encoding="utf-8")))
        for block_index,(kind,value) in enumerate(parsed):
            if doc_index==0 and kind=="paragraph" and value.startswith("Technical report "): continue
            if kind=="heading":
                level,title=value;key="ReportTitle" if level==1 else "ReportH2" if level==2 else "ReportH3"
                if doc_index==1 and title=="L Later thirty-two-slot partial-filter configurations":story.append(PageBreak())
                story.append(Paragraph(inline(title,True),s[key]))
                if doc_index==0 and level==1:
                    story.append(Paragraph(inline(publication_label(metadata,approved),True),s["ReportBody"]))
                    story.append(Paragraph(inline(publication_summary(metadata,approved),True),s["ReportBody"]))
            elif kind=="image":
                image_path=ROOT/"paper"/value[1]
                if image_path.suffix.lower()==".png":
                    fig=Image(str(image_path));scale=width/fig.imageWidth
                    fig.drawWidth=width;fig.drawHeight=fig.imageHeight*scale
                else:
                    fig=FIGURES[Path(value[1]).stem]();scale=width/fig.width
                    fig.scale(scale,scale);fig.width*=scale;fig.height*=scale
                following=parsed[block_index+1] if block_index+1<len(parsed) else None
                if following and following[0]=="paragraph" and re.match(r"^Figure\s*\d+\.",following[1]):
                    story.append(KeepTogether([fig,Spacer(1,6),Paragraph(inline(following[1],True),s["ReportBody"])]))
                else:story.extend([fig,Spacer(1,6)])
            elif kind=="table":
                t=make_table(value,s,width)
                story.append(KeepTogether([t]) if len(value)<=4 else t);story.append(Spacer(1,8))
            elif kind=="code":
                wrapped=[]
                for line in value.splitlines():wrapped.extend(textwrap.wrap(line,110,replace_whitespace=False,drop_whitespace=False,break_long_words=True) or [""])
                story.append(Preformatted("\n".join(wrapped),s["ReportCode"]))
            elif kind=="paragraph" and block_index>0 and parsed[block_index-1][0]=="image" and re.match(r"^Figure\s*\d+\.",value):
                continue  # Caption already grouped with its figure.
            else:
                body=("&#8226; " if kind=="item" else "")+inline(value,True)
                style=s["ReportItem"] if kind=="item" else s["ReportBody"]
                following=parsed[block_index+1] if block_index+1<len(parsed) else None
                if kind=="paragraph" and following and following[0]=="code" and value.rstrip().endswith(":"):
                    style=ParagraphStyle("ReportCodeLead",parent=style,keepWithNext=True)
                story.append(Paragraph(body,style))
    doc=SimpleDocTemplate(str(path),pagesize=A4,rightMargin=47,leftMargin=47,topMargin=45,bottomMargin=54,
                          title=metadata["title"],author="; ".join(c["name"] for c in metadata["approved_creators"]) if approved else "Creator metadata pending owner review",subject=publication_label(metadata,approved))
    doc.build(story,onFirstPage=footer,onLaterPages=footer)


def render_html(path):
    chunks=[]
    metadata,approved=publication_metadata()
    for index,name in enumerate(["report.md","implementation-appendix.md"]):
        chunks.append('<section id="'+("report" if index==0 else "appendix")+'">')
        for kind,value in blocks((ROOT/"paper"/name).read_text(encoding="utf-8")):
            if index==0 and kind=="paragraph" and value.startswith("Technical report "): continue
            if kind=="heading":
                level,title=value;chunks.append(f"<h{level}>{inline(title)}</h{level}>")
                if index==0 and level==1:
                    chunks.append("<p>"+inline(publication_label(metadata,approved))+"</p><p>"+inline(publication_summary(metadata,approved))+"</p>")
            elif kind=="image":
                picture=ROOT/"paper"/value[1]
                if picture.suffix.lower()==".png":
                    chunks.append('<img alt="'+html.escape(value[0],quote=True)+'" src="data:image/png;base64,'+base64.b64encode(picture.read_bytes()).decode()+'">')
                else:chunks.append(picture.read_text().split("?>",1)[-1])
            elif kind=="table":
                chunks.append("<table>")
                for j,row in enumerate(value):
                    tag="th" if j==0 else "td";chunks.append("<tr>"+"".join(f"<{tag}>{inline(c)}</{tag}>" for c in row)+"</tr>")
                chunks.append("</table>")
            elif kind=="code":chunks.append("<pre><code>"+html.escape(value)+"</code></pre>")
            elif kind=="item":chunks.append('<p class="item">&#8226; '+inline(value)+"</p>")
            else:chunks.append("<p>"+inline(value)+"</p>")
        chunks.append("</section>")
    css="""body{max-width:900px;margin:40px auto;padding:0 24px;font:16px/1.55 system-ui,sans-serif;color:#243746}h1,h2{color:#176080;line-height:1.25}h2{margin-top:2em}a{color:#176080}table{border-collapse:collapse;width:100%;font-size:14px;margin:20px 0}th,td{padding:10px;border-bottom:1px solid #d8e4e9;text-align:left;vertical-align:top}th{background:#e7f1f5}pre{background:#edf5f8;padding:15px;overflow:auto;font-size:13px}code{overflow-wrap:anywhere}p{overflow-wrap:anywhere}svg,img{max-width:100%;height:auto}section+section{border-top:2px solid #9ab6c3;margin-top:50px;padding-top:20px}.item{padding-left:16px}nav{padding:14px;background:#edf5f8} @media print{nav{display:none}body{max-width:none;font-size:11px}}"""
    path.write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(metadata["title"]+" — "+publication_label(metadata,approved))+'</title><style>'+css+'</style><body><nav>'+html.escape(publication_label(metadata,approved))+' | <a href="#report">Report</a> | <a href="#appendix">Implementation appendix</a> | <a href="../README.md">Bundle README</a></nav>'+"\n".join(chunks)+"</body></html>\n",encoding="utf-8")


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--output-dir",type=Path,required=True);args=p.parse_args()
    if args.output_dir.exists():raise SystemExit("Use a new output directory; existing reviews are preserved.")
    args.output_dir.mkdir(parents=True)
    metadata,approved=publication_metadata()
    render_pdf(args.output_dir/("pi5-receive-stream.pdf" if approved or metadata.get("status")=="prepared_not_published" else "pi5-receive-stream-draft.pdf"));render_html(args.output_dir/("release.html" if approved or metadata.get("status")=="prepared_not_published" else "review.html"))
    print(json.dumps({"output_directory":str(args.output_dir.resolve()),"publication":False}))


if __name__=="__main__":main()
