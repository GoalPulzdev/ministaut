"""Narrow, adaptive probe plans for the known Lerkendal public seating diagram.

All points are merely *candidates*. A field is counted only after a validated
visible tooltip. Coordinates do NOT encode availability values.
"""
from __future__ import annotations
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def stadium_roi(region):
    """Focus on the actual stands, not the checkout sidebar or empty map padding.

    This ratio is calibrated from the user's 22 October map screenshot. The
    browser's own measured map element is the coordinate reference.
    """
    x1,y1,x2,y2=region
    w=x2-x1;h=y2-y1
    return (max(5,round(x1+.235*w)), max(70,round(y1+.045*h)),
            round(x1+.695*w), round(y1+.79*h))


def green_pitch(region):
    x1,y1,x2,y2=region
    w=x2-x1; h=y2-y1
    # Exclude only the *middle* of the pitch on very fine passes. Its perimeter
    # stays included because some narrow section tooltips activate near edges.
    return (x1+.39*w,y1+.265*h,x1+.57*w,y1+.49*h)


def reference_points(region):
    """Transform archived probe candidates onto the current rendered map."""
    path=ROOT/'field_seeds.json'
    if not path.exists():return []
    data=json.loads(path.read_text(encoding='utf-8'))
    a,b,c,d=data['reference_region']
    x1,y1,x2,y2=region
    wx=(x2-x1)/(c-a);wy=(y2-y1)/(d-b)
    x1=max(0,x1);y1=max(0,y1)
    result=[]
    for field,p in sorted(data['points'].items()):
        x=round(x1+(p['x']-a)*wx)
        y=round(y1+(p['y']-b)*wy)
        # Measured V3 probe coordinates need one re-check; rough screenshot
        # estimates get a small 3x3 search for very narrow fields.
        is_estimated = 'estimate' in p.get('source','')
        offsets = [(0,0),(4,0),(-4,0),(0,4),(0,-4),(7,7),(-7,-7),(-7,7),(7,-7)] if is_estimated else [(0,0)]
        for ox,oy in offsets:
            result.append((x+round(ox*wx),y+round(oy*wy),field))
    return result


def scan_grid(region, spacing, exclude_pitch=False):
    x1,y1,x2,y2=region
    pitch=green_pitch(region)
    lines=[]
    y=math.ceil((y1+3)/spacing)*spacing
    while y<y2-2:
        xs=list(range(math.ceil((x1+3)/spacing)*spacing,round(x2-2),spacing))
        if len(lines)%2:xs.reverse()
        row=[]
        for x in xs:
            if exclude_pitch and pitch[0]<=x<=pitch[2] and pitch[1]<=y<=pitch[3]:
                continue
            row.append((x,y))
        lines.append(row)
        y+=spacing
    return [point for row in lines for point in row]


def missing_fields(expected,observed):
    return sorted(set(expected)-set(observed))