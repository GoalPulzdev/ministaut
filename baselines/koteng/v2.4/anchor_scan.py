"""Read-only Koteng anchor verifier with bounded per-field position recovery.

Every accepted reading must come from a fresh, stable tooltip matching the
expected section and capacity. No mouse clicks, no seat selection, no guessing
when a point cannot be validated. A recovered point is a *candidate* only.
"""
from __future__ import annotations
from dataclasses import asdict


def signatures(rows):
    return {(v.section, v.capacity, v.free) for v in rows}


def section_values(rows, section):
    return {(v.section, v.capacity, v.free) for v in rows if v.section == section}


def public_summary(rows):
    return [dict(section=s, free=f, capacity=c) for s,c,f in sorted(signatures(rows))][:18]


def recovery_offsets():
    """Short, deterministic scout around tiny stand strips (CSS pixels)."""
    return [(0,0), (0,-18), (0,18), (0,-38), (0,38),
            (0,65), (0,90), (0,115), (-15,0), (15,0),
            (-15,22), (15,22), (-30,0), (30,0),
            (-15,65), (15,65), (-30,65), (30,65)]


def point_candidates(points, viewport=None, scouts=True, hints=None, limit=18):
    """Prefer every user mark, then exact verified-history hint, then nearby probes.

    Historical hints are unverified; they must pass all hover checks each time.
    """
    seen=set();result=[]
    w,h=viewport if viewport else (10**8,10**8)
    def add(point,origin):
        point=(int(point[0]),int(point[1]))
        if 0<=point[0]<w and 0<=point[1]<h and point not in seen:
            seen.add(point);result.append((point,origin))
    for point in points:
        add(point,"manual_or_preferred")
        if len(result)>=limit:return result[:limit]
    for hint in (hints or []):
        add(hint,"historical_unverified")
        if len(result)>=limit:return result[:limit]
    if scouts:
        offsets=[o for o in recovery_offsets() if o!=(0,0)]
        for dx,dy in offsets:
            for x,y in points:
                add((x+dx,y+dy),"near_manual")
                if len(result)>=limit:return result[:limit]
    return result


def inspect_point(page, point, section, capacity, dwell_ms, read_current,
                  neutral=(6,6), alternate=None):
    page.mouse.move(*neutral)
    page.wait_for_timeout(max(120, dwell_ms))
    baseline = read_current(page)
    page.mouse.move(*point)
    page.wait_for_timeout(dwell_ms)
    first = read_current(page)
    page.wait_for_timeout(max(125, dwell_ms))
    second = read_current(page)
    left = section_values(first, section)
    right = section_values(second, section)
    expected = {v for v in left & right if v[1] == capacity}
    detail = {"point": list(point), "baseline": public_summary(baseline),
              "first": public_summary(first), "second": public_summary(second)}
    if len(left) > 1 or len(right) > 1:
        return None, "conflicting_same_section_tooltips", detail
    if len(expected) != 1:
        labels = sorted({v.section for v in second})
        if not left and not right:
            reason = "target_not_visible" if not labels else "hovered_other_section"
        elif any(v[1] != capacity for v in left | right):
            reason = "capacity_mismatch"
        else:
            reason = "target_unstable"
        return None, reason, detail
    observed = next(iter(expected))
    if observed in signatures(baseline):
        if alternate is None:
            return None, "stale_same_tooltip_at_neutral", detail
        other_point, other_name, other_capacity = alternate
        page.mouse.move(*other_point)
        page.wait_for_timeout(dwell_ms)
        other_a = read_current(page)
        page.wait_for_timeout(max(125,dwell_ms))
        other_b = read_current(page)
        other_matches = section_values(other_a, other_name) & section_values(other_b, other_name)
        detail["alternate"] = {"field": other_name, "observed": public_summary(other_b)}
        if (len(other_matches) != 1 or next(iter(other_matches))[1] != other_capacity
                or observed in signatures(other_a) or observed in signatures(other_b)):
            return None, "cannot_prove_popup_changed", detail
        page.mouse.move(*point)
        page.wait_for_timeout(dwell_ms)
        re_a=read_current(page)
        page.wait_for_timeout(max(125,dwell_ms))
        re_b=read_current(page)
        retry=section_values(re_a,section) & section_values(re_b,section)
        detail["retry"] = public_summary(re_b)
        if len(retry)!=1 or next(iter(retry))[1] != capacity or next(iter(retry)) not in expected:
            return None, "target_unstable_after_alternate", detail
        observed = next(iter(retry))
    row = next((v for v in second if (v.section,v.capacity,v.free)==observed),None)
    return row, "confirmed", detail


def scan_anchor_pass(page, anchors, reference, dwell_ms, read_current, Observation,
                     *, viewport=None, scouts=False, historical=None, preferred=None,
                     max_scout_per_section=18, only_sections=None):
    names=list(anchors)
    requested = set(names) if only_sections is None else set(only_sections)
    if not requested.issubset(set(names)):
        raise ValueError("Etterkontroll inneholder ukjent felt")
    results, discrepancies, diagnostics={}, {}, []
    count=0
    if len(names)<2:
        raise ValueError("Minst to felter kreves for uavhengig kontroll")
    for name in names:
        if name not in requested:
            continue
        samples=[]
        # A successful pass-1 candidate gets first chance in pass 2.
        base=list((preferred or {}).get(name,[])) + list(anchors[name])
        candidates=point_candidates(base,viewport,scouts,hints=(historical or {}).get(name),
                                    limit=max_scout_per_section)
        records=[]
        for point, origin in candidates:
            alternate=None
            for other in names:
                if other!=name and anchors[other]:
                    alternate=(anchors[other][0],other,reference[other]);break
            try:
                found,reason,info=inspect_point(page,point,name,reference[name],dwell_ms,read_current,
                                               alternate=alternate)
            except Exception as e:
                found,reason,info=None,"hover_exception",{"point":list(point),"error_type":type(e).__name__}
            records.append({"point":list(point),"origin":origin,"result":reason,
                            "before":info.get("baseline",[]),"at_point":info.get("second",[]),
                            **({"error_type":info["error_type"]} if "error_type" in info else {})})
            if found:
                count+=1
                samples.append(Observation(found.section,found.free,found.capacity,point[0],point[1]))
                break  # A single fresh verified point per section per pass.
        diagnostics.append({"field":name,"result":"confirmed" if samples else
                            (records[-1]["result"] if records else "no_candidates"),
                            "probe_count":len(records),"probes":records,
                            "accepted_point":list((samples[-1].x,samples[-1].y)) if samples else None})
        if samples:
            results[name]=samples[-1]
    return results, discrepancies, count, diagnostics
