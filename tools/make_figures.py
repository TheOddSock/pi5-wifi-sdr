"""Rebuild vector figures from public data using ReportLab 4.4.9.

Architecture/lifecycle are source-derived schematics. Delivery uses saved real
receipt bins. Filter response is an ideal analytical model, not an RF test.
"""
from __future__ import annotations
import cmath
import json
import math
from pathlib import Path
from reportlab.graphics import renderSVG
from reportlab.graphics.shapes import Drawing, Line, PolyLine, Polygon, Rect, String

ROOT = Path(__file__).resolve().parents[1]
BLUE = "#176080"; INK = "#243746"; GREY = "#677784"; ORANGE = "#ae5a16"
from reportlab.lib.colors import HexColor


def text(d, x, y, value, size=9, color=INK, anchor="start"):
    d.add(String(x, y, value, fontName="Helvetica", fontSize=size,
                 fillColor=HexColor(color), textAnchor=anchor))


def arrow(d, x1, y1, x2, y2):
    d.add(Line(x1,y1,x2,y2,strokeColor=HexColor(BLUE),strokeWidth=1.4))
    ang=math.atan2(y2-y1,x2-x1); head=5
    pts=[x2,y2,x2-head*math.cos(ang-.45),y2-head*math.sin(ang-.45),
         x2-head*math.cos(ang+.45),y2-head*math.sin(ang+.45)]
    d.add(Polygon(pts,fillColor=HexColor(BLUE),strokeColor=HexColor(BLUE)))


def box(d,x,y,w,h,title,lines):
    d.add(Rect(x,y,w,h,rx=4,ry=4,fillColor=HexColor("#edf5f8"),
               strokeColor=HexColor(BLUE),strokeWidth=.9))
    text(d,x+w/2,y+h-18,title,10,BLUE,"middle")
    for i,line in enumerate(lines): text(d,x+w/2,y+h-34-i*13,line,8.4,INK,"middle")


def architecture():
    d=Drawing(540,240)
    box(d,4,144,157,76,"D11 collector",["Circular source sample RAM","16,384 packed complex words","Continues writing during export"])
    box(d,192,144,157,76,"Embedded Cortex-R4",["Guarded source selection/filter","Incremental word checksum","Native watchdog and reader lease"])
    box(d,380,144,157,76,"Owned publication RAM",["Eight reusable 1,024-word slots","Sequence committed after payload","128-word stopped reference"])
    arrow(d,163,182,189,182);arrow(d,351,182,377,182)
    box(d,380,27,157,76,"Linux private reader",["SDIO Function1 concurrent reads","Double copy and metadata checks","Exact next sequence or refusal"])
    box(d,192,27,157,76,"Userspace worker",["Bounded acquisition/write queue","4,176-byte framed records","Fixed requested frame quota"])
    box(d,4,27,157,76,"Saved evidence",["Complete framed recording","Receipt times and stop summary","Archive and health audit"])
    arrow(d,458,141,458,106);arrow(d,377,65,351,65);arrow(d,189,65,163,65)
    text(d,270,4,"Schematic: native capture request stays active until normal completion",8,GREY,"middle")
    return d


def lifecycle():
    d=Drawing(540,145)
    stages=[("Admit",["Identity / ownership"]),("Arm",["Save and set controls"]),
            ("Stream",["Publish / read / renew"]),("Stop",["Block-aligned end"]),
            ("Reference",["Latest retained tail"]),("Restore",["Genuine completion"])]
    for i,(title,lines) in enumerate(stages):
        x=3+i*90;box(d,x,57,82,60,title,lines)
        if i<5:arrow(d,x+84,87,x+88,87)
    text(d,270,31,"STOP or lease expiry ends collection; failures preserve a separate recovery record",8.2,GREY,"middle")
    text(d,270,13,"Explanatory order only. It is not a measured time trace.",8.2,GREY,"middle")
    return d


def axes(d,xmin,xmax,ymin,ymax,xlabel,ylabel,xticks,yticks):
    left,bottom,w,h=65,48,455,165
    def point(x,y):return left+w*(x-xmin)/(xmax-xmin),bottom+h*(y-ymin)/(ymax-ymin)
    for x,label in xticks:
        px,py=point(x,ymin);d.add(Line(px,bottom,px,bottom+h,strokeColor=HexColor("#e6ecef"),strokeWidth=.5))
        text(d,px,bottom-15,label,8,GREY,"middle")
    for y,label in yticks:
        px,py=point(xmin,y);d.add(Line(left,py,left+w,py,strokeColor=HexColor("#e6ecef"),strokeWidth=.5))
        text(d,left-8,py-3,label,8,GREY,"end")
    d.add(Line(left,bottom,left+w,bottom,strokeColor=HexColor(INK)))
    d.add(Line(left,bottom,left,bottom+h,strokeColor=HexColor(INK)))
    text(d,left+w/2,9,xlabel,9,INK,"middle");text(d,left,234,ylabel,9)
    return point


def delivery():
    bins=json.loads((ROOT/"evidence/derived/sixstream-c-delivery.json").read_text())["bins"]
    d=Drawing(540,250)
    point=axes(d,0,300,3.329,3.335,"Relative host receipt window (seconds)",
               "Payload received per complete one-second window (decimal MB)",
               [(k,str(k)) for k in range(0,301,60)],[(v,f"{v:.3f}") for v in [3.329,3.331,3.333,3.335]])
    pts=[]
    for b in bins:pts.extend(point(b["relative_second"]+.5,b["payload_bytes"]/1000000))
    d.add(PolyLine(pts,strokeColor=HexColor(BLUE),strokeWidth=.7,fillColor=None))
    text(d,518,219,"Sixstream C: real receipt bins",8,BLUE,"end")
    return d


def filter_response():
    d=Drawing(540,265)
    point=axes(d,0,4,-60,0,"Frequency / nominal output word rate", "Ideal linear amplitude response (dB)",
               [(k,str(k)) for k in range(5)],[(k,str(k)) for k in [-60,-40,-20,0]])
    six=[(i,w/8) for i,w in enumerate([1,1,2,2,1,1])]
    sparse=[(i,.25) for i in [0,1,8,9]]
    for weights,color in [(six,BLUE),(sparse,ORANGE)]:
        pts=[]
        for i in range(801):
            x=i/200;z=sum(w*cmath.exp(-2j*math.pi*x*n/16) for n,w in weights)
            y=max(-60,20*math.log10(max(abs(z),1e-15)));pts.extend(point(x,y))
        d.add(PolyLine(pts,strokeColor=HexColor(color),strokeWidth=1.1,fillColor=None))
    text(d,78,219,"Six input: [1,1,2,2,1,1]/8",8,BLUE)
    text(d,315,219,"Sparse: offsets 0,1,8,9",8,ORANGE)
    text(d,270,251,"Analytical model; excludes integer rounding and physical receiver",8,GREY,"middle")
    return d


FIGURES={"architecture":architecture,"lifecycle":lifecycle,"delivery":delivery,"filter-response":filter_response}


def main():
    directory=ROOT/"paper/figures";directory.mkdir(parents=True,exist_ok=True)
    for name,fn in FIGURES.items():renderSVG.drawToFile(fn(),str(directory/(name+".svg")))
    print(json.dumps({"figures":list(FIGURES),"format":"SVG","RF_measurements_generated":False}))


if __name__=="__main__":main()
