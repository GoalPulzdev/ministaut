"""Read-only seat availability trend, cautious match-day forecast and offline chart.

All observations must already be complete and published; never extrapolate from
partially-scanned seats or mixed away-section configurations.
"""
from __future__ import annotations
import html
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path

MAX_SEATED = 19015
MIN_POINTS = 4
MIN_SPAN_HOURS = 6
MAX_FORECAST_DAYS = 14


def fmt(value):
    return format(int(value), ',').replace(',', ' ')


def parse_time(value):
    if not value:return None
    try:
        dt=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return dt.astimezone(timezone.utc) if dt.utcoffset() is not None else None
    except (ValueError,TypeError,OverflowError):return None


def kickoff_time(match_date):
    """Parse Norwegian match time, using Oslo DST through IANA zone database."""
    import re
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    m=re.search(r'(\d{2})[./](\d{2})[./](\d{4})\s*(?:kl\.?\s*)?(\d{1,2}):(\d{2})',str(match_date or ''))
    if not m:return None
    try:
        local=datetime(int(m[3]),int(m[2]),int(m[1]),int(m[4]),int(m[5]),tzinfo=ZoneInfo('Europe/Oslo'))
        return local.astimezone(timezone.utc)
    except (ValueError,ZoneInfoNotFoundError):return None


def scoped_records(records, locked=(), total=21423, standing='unknown'):
    """Exactly one event is supplied by the caller; reject pre-V18 unscoped imports."""
    candidates={}
    for record in records:
        if not isinstance(record,dict):continue
        dt=parse_time(record.get('time_utc'))
        available=record.get('available_seated')
        if not dt or not isinstance(available,int) or isinstance(available,bool):continue
        if not 0<=available<=MAX_SEATED:continue
        if record.get('total')!=total or record.get('standing_availability')!=standing:continue
        if not isinstance(record.get('locked_fields'),list):continue
        if sorted(record['locked_fields'])!=sorted(locked):continue
        candidates[dt]= {'time_utc':dt.isoformat(timespec='seconds'), 'free':available}
    return sorted(candidates.values(),key=lambda r:r['time_utc'])


def forecast(records, match_date, locked=(), total=21423):
    """Median pairwise slope gives a robust *illustrative* projection, not sales.

    Refuse precise far-future extrapolation. 'band' is a heuristic scenario
    spread, explicitly not a confidence interval or guaranteed outcome.
    """
    points=scoped_records(records,locked,total)
    response={'state':'insufficient','points':points,'count':len(points),'value':None,
              'low':None,'high':None,'daily_change':None,'kickoff_utc':None,
              'message':'Trenger minst fire sammenlignbare målinger over minst seks timer.'}
    kickoff=kickoff_time(match_date)
    if kickoff is None:
        response.update(state='no_kickoff',message='Kampstart kan ikke fastslås sikkert.');return response
    response['kickoff_utc']=kickoff.isoformat(timespec='seconds')
    if not points:return response
    latest=parse_time(points[-1]['time_utc']);hours=(kickoff-latest).total_seconds()/3600
    response['hours_until']=round(hours,1)
    if hours<=0:
        response.update(state='passed',message='Kampstart er passert.');return response
    if len(points)<MIN_POINTS:return response
    # Most recent 14 days / at most 56 samples, never use historical bulk import.
    window=[p for p in points if (latest-parse_time(p['time_utc'])).total_seconds() <=14*86400][-56:]
    span=(parse_time(window[-1]['time_utc'])-parse_time(window[0]['time_utc'])).total_seconds()/3600
    if len(window)<MIN_POINTS or span<MIN_SPAN_HOURS:return response
    rates=[]
    for i in range(len(window)):
        for j in range(i+1,len(window)):
            gap=(parse_time(window[j]['time_utc'])-parse_time(window[i]['time_utc'])).total_seconds()/86400
            if gap>=2/24:
                rates.append((window[j]['free']-window[i]['free'])/gap)
    if not rates:return response
    rate=statistics.median(rates)
    response['daily_change']=round(rate)
    if hours>MAX_FORECAST_DAYS*24:
        response.update(state='too_far',message='Mer enn 14 dager til avspark. Viser utvikling, men ingen pålitelig kampstartprognose.');return response
    current=window[-1]['free']
    projected=max(0,min(MAX_SEATED,current+rate*hours/24))
    mad=statistics.median(abs(x-rate) for x in rates)
    spread=max(80,abs(rate)*hours/24*.35,1.5*mad*hours/24)
    # Conservative heuristic band grows with projection time, capped at physical limits.
    lower=max(0,math.floor(projected-spread))
    upper=min(MAX_SEATED,math.ceil(projected+spread))
    response.update(state='estimate',value=round(projected),low=lower,high=upper,
                    message='Grovt scenario, ikke garantert prognose. Endringer i kvoter og reservasjoner kan gi store avvik.')
    return response


def create_chart_html(records, match_title, match_date, key, locked=(), total=21423):
    result=forecast(records,match_date,locked,total)
    points=result['points']; safe=html.escape
    width,height=1050,420
    left,right,top,bottom=68,34,25,60
    plotw,ploth=width-left-right,height-top-bottom
    times=[parse_time(p['time_utc']).timestamp() for p in points]
    values=[p['free'] for p in points]
    if result['state']=='estimate' and result['kickoff_utc']:
        times.append(parse_time(result['kickoff_utc']).timestamp());values.extend([result['low'],result['high']])
    if not times:times=[0,1];values=[0,1]
    tmin,tmax=min(times),max(times)
    if tmax<=tmin:tmax=tmin+1
    ymin=max(0,min(values)-max(100,(max(values)-min(values))*.15))
    ymax=min(MAX_SEATED,max(values)+max(100,(max(values)-min(values))*.15))
    if ymax<=ymin:ymax=ymin+100
    def xy(time,free):return (round(left+(time-tmin)/(tmax-tmin)*plotw,1), round(top+(ymax-free)/(ymax-ymin)*ploth,1))
    path=' '.join(('M' if i==0 else 'L')+'%.1f,%.1f'%xy(parse_time(p['time_utc']).timestamp(),p['free']) for i,p in enumerate(points))
    lines=[]
    for i in range(5):
        y=round(top+i*ploth/4,1); val=round(ymax-i*(ymax-ymin)/4)
        lines.append(f'<line x1="{left}" y1="{y}" x2="{width-right}" y2="{y}" stroke="#315e49" stroke-opacity=".6"/><text x="{left-11}" y="{y+5}" text-anchor="end" fill="#abc5b4" font-size="15">{fmt(val)}</text>')
    dots=''.join('<circle cx="%.1f" cy="%.1f" r="5" fill="#48f0a4"><title>%s · %s ledige</title></circle>'%(*xy(parse_time(p['time_utc']).timestamp(),p['free']),safe(p['time_utc']),fmt(p['free'])) for p in points)
    extra=''
    if result['state']=='estimate':
        future=parse_time(result['kickoff_utc']).timestamp();x0,y0=xy(parse_time(points[-1]['time_utc']).timestamp(),points[-1]['free']);x1,y1=xy(future,result['value'])
        _,yl=xy(future,result['low']);_,yh=xy(future,result['high'])
        extra=f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y1}" stroke="#f9bc62" stroke-width="3" stroke-dasharray="9 7"/><line x1="{x1}" y1="{yh}" x2="{x1}" y2="{yl}" stroke="#f9bc62" stroke-width="9" stroke-opacity=".45"/><circle cx="{x1}" cy="{y1}" r="7" fill="#f9bc62"/>'
    from zoneinfo import ZoneInfo
    oslo=ZoneInfo('Europe/Oslo')
    axis=[]
    for i in range(5):
        val=tmin+i*(tmax-tmin)/4
        dt=datetime.fromtimestamp(val,tz=oslo)
        axis.append(f'<text x="{left+i*plotw/4:.1f}" y="{height-16}" text-anchor="{'start' if i==0 else 'end' if i==4 else 'middle'}" fill="#92b49f" font-size="15">{dt:%d.%m %H:%M}</text>')
    if result['state']=='estimate':
        forecast_label=f'<strong>{fmt(result['value'])} ledige ved avspark</strong><span>Grovt scenario: {fmt(result['low'])}–{fmt(result['high'])} · anslått {result["daily_change"]:+} plasser/døgn</span>'
    else:
        forecast_label=f'<strong>Prognose: ikke beregnet</strong><span>{safe(result["message"])}</span>'
    rows=''.join(f'<tr><td>{parse_time(p["time_utc"]).astimezone(oslo):%d.%m.%Y %H:%M}</td><td>{fmt(p['free'])}</td><td>{fmt(total-p['free'])} *</td></tr>' for p in reversed(points))
    return f'''<!doctype html><html lang="nb"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>RBK Billettmonitor – historikk</title><style>
    body{{font:16px system-ui,sans-serif;color:#eaffee;background:#071510;margin:0;padding:25px}}main{{max-width:1150px;margin:auto}}h1{{font-size:35px;margin:4px 0}}.meta{{color:#91baa6}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:13px;margin:25px 0}}.card{{border:1px solid #35694d;background:#10291e;border-radius:15px;padding:17px}}.card strong{{display:block;font-size:23px;color:#6cf2b5}}.card span{{font-size:13px;color:#acccbb}}svg{{width:100%;height:auto;background:#0b2119;border:1px solid #31563f;border-radius:15px}}table{{width:100%;border-collapse:collapse;margin:15px 0}}td,th{{text-align:left;padding:11px;border-bottom:1px solid #335641}}small{{color:#9dc3ae}}.note{{line-height:1.6;color:#bed0c3;margin:18px 0}}@media(max-width:620px){{body{{padding:12px}}h1{{font-size:25px}}}}</style></head><body><main><p class="meta">LERKENDAL · UTVIKLING I LEDIGE PLASSER</p><h1>{safe(match_title)}</h1><p class="meta">Kamp: {safe(match_date)} · {len(points)} sammenlignbare målinger · oppdateres ved godkjent skanning</p><div class="cards"><div class="card"><span>Sist dokumentert ledige sitteplasser</span><strong>{fmt(points[-1]['free']) if points else '–'}</strong></div><div class="card"><span>Prognose ved kampstart</span>{forecast_label}</div><div class="card"><span>Utvikling siste målinger</span><strong>{('+' if points[-1]['free']>points[0]['free'] else '')+fmt(points[-1]['free']-points[0]['free']) if len(points)>=2 else '–'}</strong><span>Endring i tilgjengelige plasser; ikke dokumenterte salg</span></div></div><svg viewBox="0 0 {width} {height}" role="img" aria-label="Tidsserie med ledige plasser og eventuell stiplet prognose"><g>{''.join(lines)}</g><path d="{path}" fill="none" stroke="#48f0a4" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>{dots}{extra}{''.join(axis)}</svg><p class="note">Grønn kurve er faktiske godkjente målinger. Stiplet oransje linje er et usikkert scenario, ikke et måleresultat. Historikk fra endret bortefeltoppsett holdes utenfor. * Estimert ikke tilgjengelige = 21 423 minus avleste ledige sitteplasser, ikke RBKs offisielle salgstall. Ståplassledighet er ukjent.</p><h2>Målehistorikk</h2><table><thead><tr><th>Tidspunkt (Oslo)</th><th>Ledige</th><th>Estimert ikke tilgjengelige *</th></tr></thead><tbody>{rows}</tbody></table><small>Kun historikk fra samme kamp og samme bekreftede bortefeltoppsett inngår.</small></main></body></html>'''


def save_chart(root:Path,records:list[dict],match_title:str,match_date:str,key:str,locked=(),total=21423):
    folder=Path(root);folder.mkdir(parents=True,exist_ok=True)
    path=folder/'billettutvikling.html'
    path.write_text(create_chart_html(records,match_title,match_date,key,locked,total),encoding='utf-8')
    return path