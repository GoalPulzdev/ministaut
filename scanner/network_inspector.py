"""Privacy-safe schema-only inspection of public GETs already loaded by the page.

NO extra HTTP requests. Never export response bodies, identifiers, tokens,
seat details, cookies, authorization headers, or checkout state.
"""
from __future__ import annotations
import re
from urllib.parse import urlparse

_OBJECT_KEY=re.compile(r'^(?:[0-9a-f]{12,}|[0-9a-f]{8}\-[0-9a-f-]{27,}|[A-Za-z0-9_-]{32,})$',re.I)

def safe_key(key):
    return '<opaque-id>' if _OBJECT_KEY.fullmatch(key) else key

_ALLOWED=re.compile(r'^/api/public/event/[A-Za-z0-9_-]+/(?:map|resources|status|contingents)(?:/|$)')


def shape(value, depth=0):
    if depth>=4:return type(value).__name__
    if isinstance(value,dict):
        keys=sorted(str(k) for k in value)
        samples={}
        # Only structural shapes, NEVER actual scalar values.
        for k in keys[:12]:
            if k not in value:continue
            v=value[k]
            samples[safe_key(k)]=shape(v,depth+1) if isinstance(v,(dict,list)) else type(v).__name__
        return {'type':'object','property_count':len(keys),'keys':[safe_key(k) for k in keys[:20]],'sample_types':samples}
    if isinstance(value,list):
        return {'type':'array','length':len(value),
                'first_item':shape(value[0],depth+1) if value else None}
    return type(value).__name__


def capture(response, diagnostics):
    try:
        if response.request.method!='GET' or response.status!=200:return
        url=urlparse(response.url)
        if url.hostname!='seatmap.vivenu.com' or not _ALLOWED.match(url.path):return
        suffix=url.path.rsplit('/',1)[-1]
        if suffix not in ('map','resources','status','contingents'):return
        ct=(response.headers.get('content-type') or '').lower()
        if not ('json' in ct):return
        size=int(response.headers.get('content-length') or '0')
        if size>8_000_000:
            diagnostics.setdefault('public_response_schemas',{})[suffix]={'skipped':'body larger than 8MB'}
            return
        data=response.json()
        diagnostics.setdefault('public_response_schemas',{})[suffix]=shape(data)
    except Exception as exc:
        diagnostics.setdefault('public_response_schemas',{})[suffix]={'inspection_error':type(exc).__name__}