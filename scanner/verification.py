"""Confirm hover-derived field counts with a fresh popup after moving away.

A rapidly moving pointer can leave the previous tooltip on the screen. Do not
attribute that stale tooltip to the new coordinate.
"""
from __future__ import annotations
from parser import parse_tooltip


def parse_visible_texts(texts,source,x,y):
    hits=[]
    seen=set()
    for text in texts:
        value=parse_tooltip(text,source,x,y)
        if value:
            key=(value.section,value.capacity,value.free)
            if key not in seen:
                seen.add(key);hits.append(value)
    return hits


def confirm_fresh_hover(page, read_text, candidate, x, y, hover_ms=90):
    """Return confirmed observation or None; never click on a seat.

    Confirmation is deliberately conservative: the previous popup must hide
    at a neutral, off-map position and the target's label must reappear.
    """
    viewport=page.viewport_size or {'width':1360,'height':740}
    neutral=(viewport['width']-30, viewport['height']-30)
    page.mouse.move(*neutral)
    cleared=False
    for _ in range(4):
        page.wait_for_timeout(95)
        if not parse_visible_texts(read_text(page),'neutral',-1,-1):
            cleared=True;break
    if not cleared:
        return None
    page.mouse.move(x,y)
    match=None
    for delay in (max(130,hover_ms),95):
        page.wait_for_timeout(delay)
        hits=parse_visible_texts(read_text(page),'verified',x,y)
        for hit in hits:
            if (hit.section==candidate.section and hit.capacity==candidate.capacity and
                    abs(hit.free-candidate.free)<=2):
                match=hit
                break
        if match:break
    return match