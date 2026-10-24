"""RBK Billettmonitor V20: repeating hourly schedule and forecast charts.

Connects to an Edge instance started in remote-debugging mode. An isolated
Edge profile is started automatically when needed. Never clicks on a seat.
"""
from __future__ import annotations
import argparse,csv,html,json,os,re,subprocess,sys,threading
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from time import monotonic,sleep
from urllib.parse import urlparse
from urllib.request import urlopen
from pitch_locator import Pitch,locate,to_screen,to_reference
from parser import Counts
from verification import parse_visible_texts
from hover_sampler import HoverTransitionSampler
from scanner import read_text,choose_map_region,frame_transform
from targets_v16 import confirmed_load,field_candidates,round_robin_recovery,record_verified
from publication import publish, TOTAL_PLACES, event_labels, event_key, load_history
from match_config import SEATS,load_locked,save_locked,normalize_locked,check_map_against_reference
from schedule_control import ScanSchedule
from event_registry import EventRegistry
from analytics import forecast,save_chart,scoped_records

ROOT=Path(__file__).resolve().parent
KNOWN=json.loads((ROOT/'anchors_v15.json').read_text(encoding='utf-8'))
OLD=json.loads((ROOT/'field_seeds.json').read_text(encoding='utf-8'))['points']
PANEL=(ROOT/'panel.js').read_text(encoding='utf-8')
CONFIRMED_POINTS=confirmed_load(ROOT/'bekreftede_posisjoner_v16.json')
PATTERN=re.compile(r'^/api/public/event/[A-Za-z0-9_-]+/map/?$')

def checkout_url(url):
    u=urlparse(url)
    return u.scheme=='https' and u.hostname=='billett.rbk.no' and u.path.startswith('/checkout/')

def local_debug_ready(port):
    try:
        with urlopen(f'http://127.0.0.1:{port}/json/version',timeout=.6) as resp:data=json.load(resp)
        return 'Edg/' in data.get('Browser','')
    except Exception:return False

def find_edge():
    for loc in (os.getenv('PROGRAMFILES(X86)'),os.getenv('PROGRAMFILES'),os.getenv('LOCALAPPDATA')):
        if loc:
            e=Path(loc)/'Microsoft'/'Edge'/'Application'/'msedge.exe'
            if e.is_file():return str(e)
    return None

def start_edge(url,port,edge_path,attach_only):
    if local_debug_ready(port):return False
    if attach_only:raise RuntimeError('Ingen åpen debug-Edge. Bruk START_HURTIGKART.bat først.')
    exe=edge_path or find_edge()
    if not exe:raise RuntimeError('Microsoft Edge ble ikke funnet. Bruk --edge-path ved behov.')
    user_dir=ROOT/'edge_scanner_profile';user_dir.mkdir(exist_ok=True)
    flags=[exe,f'--remote-debugging-port={port}','--remote-debugging-address=127.0.0.1',
           f'--user-data-dir={user_dir}','--no-first-run','--no-default-browser-check','--new-window',url]
    subprocess.Popen(flags,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                     creationflags=0x00000008 if sys.platform.startswith('win') else 0)
    for i in range(80):
        if local_debug_ready(port):return True
        sleep(.25)
    raise RuntimeError('Klarte ikke å aktivere lokal Edge-feilsøking. Sjekk Edge/vinduet og firmapolicy.')

class Collector:
    def __init__(self):self.map=None;self.error=''
    def callback(self,response):
        try:
            u=urlparse(response.url)
            if u.scheme!='https' or u.hostname!='seatmap.vivenu.com' or not PATTERN.fullmatch(u.path):return
            if response.request.method!='GET' or response.status!=200:return
            body=response.body()
            if len(body)>12_000_000:return
            val=json.loads(body)
            if isinstance(val,dict):self.map=val
        except Exception as ex:self.error=type(ex).__name__

def expected_from_map(mapdata):
    root=mapdata.get('seatMap',mapdata)
    names=set();cap={};stands=set()
    for layer in root.get('layers',[]):
        if not isinstance(layer,dict):continue
        for sec in layer.get('sections',[]):
            if not isinstance(sec,dict) or not sec.get('name'):continue
            name=sec['name'].strip().upper();names.add(name)
            count=sum(len(row.get('seats',[])) for group in sec.get('groups',[]) if isinstance(group,dict)
                      for row in group.get('rows',[]) if isinstance(row,dict))
            if count:cap[name]=count
        for ga in layer.get('ga',[]):
            if isinstance(ga,dict) and ga.get('name'):stands.add(ga['name'].strip().upper())
    return names,cap,stands

def panel_install(page):
    try:page.evaluate(PANEL)
    except Exception:return False
    js="""() => {if(window.__rbkMouseTracker)return;
        window.__rbkMouseTracker={x:-1,y:-1,t:0};
        document.addEventListener('mousemove',e=>{const m=window.__rbkMouseTracker;m.x=e.clientX;m.y=e.clientY;m.t=Date.now();},true)}"""
    for frame in page.frames:
        try:frame.evaluate(js)
        except Exception:pass
    return True

def mouse_location(page):
    best={'x':-1,'y':-1,'t':0}
    for frame in page.frames:
        try:
            loc=frame.evaluate('() => window.__rbkMouseTracker || null')
            if isinstance(loc,dict) and loc.get('t',0)>best['t']:
                ox,oy,sx,sy=frame_transform(frame)
                best={'x':round(ox+loc['x']*sx),'y':round(oy+loc['y']*sy),'t':loc['t']}
        except Exception:continue
    return best

def panel_show(page,data):
    """Update the pinned dashboard without destroying edited fields or commands."""
    js = r"""data => {const root=document.getElementById('rbk-v16-live-panel');if(!root)return false;
      const put=(id,v)=>{const e=root.querySelector('#'+id);if(e)e.textContent=String(v)};
      const number=v=>Number(v).toLocaleString('nb-NO');
      const list=root.querySelector('#rbk-saved-events');
      if(list){
        const selection=list.value;
        const items=data.registered_events||[];
        const signature=JSON.stringify(items);
        if(list.dataset.signature!==signature){
          list.dataset.signature=signature;
          list.replaceChildren();
          const placeholder=document.createElement('option');placeholder.value='';placeholder.textContent='Velg lagret kamp';list.append(placeholder);
          for(const event of items){
            const option=document.createElement('option');option.value=event.key;
            const state=event.status==='finished'?' · ferdig':event.status==='awaiting_kickoff'?' · angi avspark':event.status==='awaiting_map'?' · kartlegging':' · aktiv';
            option.textContent=event.title+state;
            list.append(option);
          }
          const current=items.find(e=>e.key===data.event_key);
          if(items.some(e=>e.key===selection))list.value=selection;
          else if(current)list.value=current.key;
        }
      }
      put('rbk-title',data.title||'Rosenborg · Billettstatus');
      put('rbk-match-id',data.match_date||data.event_key||'');
      put('rbk-mode',data.mode);put('rbk-found',(data.covered??data.found??0)+'/'+data.total);
      put('rbk-locked-count',data.locked||0);put('rbk-free',number(data.free));
      put('rbk-free-label',data.complete?'Ledige sitteplasser':'Foreløpig i avleste felt');
      put('rbk-estimated',data.complete?number(data.estimated):'–');
      put('rbk-missing-total','('+data.missing.length+')');
      put('rbk-missing-count',data.missing.length+' mangler'+(data.conflicts?' · '+data.conflicts+' konflikter':''));
      put('rbk-last',data.last||'Ingen felt registrert ennå');
      put('rbk-last-time',data.clock||'');
      put('rbk-delta',data.delta===null?'–':(data.delta>0?'+':'')+number(data.delta));
      put('rbk-delta-label',data.delta_label||'Vises ved komplett måling');
      const F=data.forecast||{};
      const number2=v=>Number(v).toLocaleString('nb-NO');
      put('rbk-forecast-num',F.state==='estimate'?number2(F.value)+' ledige':'Avventer prognose');
      put('rbk-forecast-note',F.state==='estimate'
        ?'Grovt scenario '+number2(F.low)+'–'+number2(F.high)+' ledige ved avspark. Endring '+(F.daily_change>0?'+':'')+number2(F.daily_change)+' per døgn. Ikke en garanti.'
        :(F.message||'Behøver flere målinger.'));
      const toggle=root.querySelector('#rbk-auto-toggle');if(toggle){toggle.textContent=data.auto_enabled?'På':'Av';toggle.setAttribute('aria-pressed',String(Boolean(data.auto_enabled)));}
      root.dataset.autoEnabled=String(Boolean(data.auto_enabled));
      root.dataset.nextScanAt=(data.auto_enabled && data.auto_remaining!==null && data.auto_remaining!==undefined)?String(Date.now()+Number(data.auto_remaining)*1000):'';
      const node=root.querySelector('#rbk-auto-next');if(node){if(!data.auto_enabled)node.textContent='Avslått · bare manuelle sjekker';else if(data.auto_remaining==null)node.textContent='Planlegger neste sjekk …';else{const secs=Math.max(0,Number(data.auto_remaining));node.textContent='Neste om '+Math.floor(secs/3600)+' t '+Math.floor((secs%3600)/60)+' min';}}
      const chartHost=root.querySelector('#rbk-history-chart');if(chartHost){chartHost.replaceChildren();
        const points=(data.chart_points||[]).map(p=>({t:Date.parse(p.time_utc),v:Number(p.free)})).filter(p=>Number.isFinite(p.t)&&Number.isFinite(p.v));
        const forecastTarget=F.state==='estimate'&&F.kickoff_utc?{t:Date.parse(F.kickoff_utc),v:Number(F.value)}:null;
        const all=forecastTarget&&Number.isFinite(forecastTarget.t)?points.concat([forecastTarget]):points;
        const ns='http://www.w3.org/2000/svg';
        const add=(tag,attrs,value)=>{const e=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,String(v));if(value!==undefined)e.textContent=value;chartHost.appendChild(e);return e;};
        if(points.length){
          const minT=Math.min(...all.map(x=>x.t)),maxT=Math.max(...all.map(x=>x.t)),spreadT=Math.max(1,maxT-minT);
          const vals=all.map(x=>x.v),minV=Math.min(...vals),maxV=Math.max(...vals),spreadV=Math.max(50,maxV-minV);
          const pos=p=>[8+300*(p.t-minT)/spreadT,105-86*(p.v-minV)/spreadV];
          for(let i=0;i<3;i++){const y=20+i*43;add('line',{x1:8,y1:y,x2:308,y2:y,stroke:'#345744','stroke-dasharray':'3 5'});}
          if(points.length>=2)add('polyline',{points:points.map(p=>pos(p).map(v=>v.toFixed(1)).join(',')).join(' '),fill:'none',stroke:'#58f3af','stroke-width':2.8,'stroke-linecap':'round'});
          for(const p of points.slice(-14)){const [x,y]=pos(p);let c=add('circle',{cx:x,cy:y,r:2.7,fill:'#adffd8'});const ti=document.createElementNS(ns,'title');ti.textContent=new Date(p.t).toLocaleString('nb-NO')+' · '+number2(p.v)+' ledige';c.appendChild(ti);}
          if(forecastTarget&&Number.isFinite(forecastTarget.t)){const [x,y]=pos(points[points.length-1]),[fx,fy]=pos(forecastTarget);add('line',{x1:x,y1:y,x2:fx,y2:fy,stroke:'#fac86b','stroke-width':2.2,'stroke-dasharray':'6 5'});add('circle',{cx:fx,cy:fy,r:4,fill:'#fac86b'});}
          add('text',{x:8,y:117,fill:'#a9cbb8','font-size':9},new Date(minT).toLocaleDateString('nb-NO'));
          add('text',{x:308,y:117,fill:'#a9cbb8','font-size':9,'text-anchor':'end'},new Date(maxT).toLocaleDateString('nb-NO'));
        }else add('text',{x:16,y:62,fill:'#91b69f','font-size':11},'Historikken bygges opp …');
      }
      let bar=root.querySelector('#rbk-track');if(bar)bar.style.width=(data.total?100*(data.covered??data.found??0)/data.total:0)+'%';
      let host=root.querySelector('#rbk-missing');if(host){host.replaceChildren();
       for(const name of data.missing){const b=document.createElement('button');b.textContent=name;
         b.dataset.action='field:'+name;b.title='Prøv nytt treffpunkt for '+name;host.appendChild(b)}
       if(!data.missing.length)host.textContent='Alle felt avklart';}
      root.classList.toggle('busy',Boolean(data.busy));
      let b=root.querySelector('[data-action="new_scan"]');if(b)b.disabled=Boolean(data.busy);
      const scope=data.event_key||'';
      if(window.__rbkHUD.configScope!==scope){window.__rbkHUD.configScope=scope;
        let locked=root.querySelector('#rbk-locked-input');if(locked)locked.value=(data.locked_names||[]).join(',');
        let sw=root.querySelector('#rbk-switch-url');if(sw)sw.value='';}
      if(root.querySelector('#rbk-locked-input') && document.activeElement!==root.querySelector('#rbk-locked-input') && !data.busy){
        // Reflected config changes are only applied after a new scan.
        root.querySelector('#rbk-locked-input').dataset.lastKnown=(data.locked_names||[]).join(',');}
      const svg=root.querySelector('#rbk-spark');if(svg){svg.replaceChildren();
        const vals=data.chart||[];if(vals.length>=2){
          const hi=Math.max(...vals),lo=Math.min(...vals),denom=Math.max(hi-lo,1);
          const points=vals.map((val,i)=>(5+i*118/(vals.length-1)).toFixed(1)+','+(43-(val-lo)*36/denom).toFixed(1)).join(' ');
          const ns='http://www.w3.org/2000/svg';const poly=document.createElementNS(ns,'polyline');
          poly.setAttribute('points',points);poly.setAttribute('fill','none');poly.setAttribute('stroke','#4befa8');
          poly.setAttribute('stroke-width','2.6');poly.setAttribute('stroke-linecap','round');svg.appendChild(poly);
          const last=points.split(' ').at(-1).split(',');const circle=document.createElementNS(ns,'circle');
          circle.setAttribute('cx',last[0]);circle.setAttribute('cy',last[1]);circle.setAttribute('r','3.5');
          circle.setAttribute('fill','#c9ffe2');svg.appendChild(circle);
        }else{const t=document.createElementNS('http://www.w3.org/2000/svg','text');t.setAttribute('x','7');t.setAttribute('y','28');
        t.setAttribute('fill','#86af99');t.setAttribute('font-size','10');t.textContent='Historikk bygges opp';svg.appendChild(t);}};
      return true;}"""
    try:
        if not page.evaluate(js,data):panel_install(page);page.evaluate(js,data)
    except Exception:
        panel_install(page)
        page.evaluate(js,data)

def panel_command(page):
    try:return page.evaluate("() => {const v=window.__rbkHUD;if(!v)return '';let c=v.command;v.command='';return c||''}")
    except Exception:return ''

def dom_labels(page,known):
    js="""() => [...document.querySelectorAll('svg text,svg tspan')].map(el=>{
      const r=el.getBoundingClientRect();return {name:(el.textContent||'').trim().toUpperCase(),x:r.left+r.width/2,y:r.top+r.height/2,w:r.width}})
      .filter(a=>a.w>2&&a.w<120)"""
    found={}
    for frame in page.frames:
        try:
            ox,oy,sx,sy=frame_transform(frame)
            for data in frame.evaluate(js):
                if data['name'] in known:
                    found.setdefault(data['name'],[]).append((round(ox+data['x']*sx),round(oy+data['y']*sy)))
        except Exception:continue
    return found

def learned_load(path):
    if not path.is_file():return {}
    try:return json.loads(path.read_text(encoding='utf-8')).get('fields',{})
    except Exception:return {}

def learned_save(path,points):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps({'version':15,'fields':points},ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(path)

def save_reports(out,counts,expected,cap,standing,url,source,nprobe,mode,pitch,probe_metrics=None,
                 locked=(),map_verified=False,map_issues=None,locked_conflicts=None):
    v=counts.export();captured=set(counts._groups);missing=sorted(expected-captured-set(locked))
    data={'url':url,'time_utc':datetime.now(timezone.utc).isoformat(timespec='seconds'),
          'mode':mode,'expected_from':source,'expected_fields':len(expected),
          'captured_fields':len(captured&expected),'covered_fields':len((captured&expected)|set(locked)),
          'missing_fields':missing,'locked_fields':sorted(locked),
          'locked_fields_confirmed':True if locked else False,
          'map_structure_verified':bool(map_verified),'map_structure_issues':map_issues or {},
          'standing_separate':sorted(standing),'confirmed_fields':v['fields'],
          'conflicts':dict(v['conflicts'], **(locked_conflicts or {})),'free_confirmed_fields':v['free_seats_confirmed'],
          'free_min':v['free_seats_min'],'free_max':v['free_seats_max'],
          'capacity_verified_fields':v['capacity_confirmed'],'map_field_capacities':cap,
          'automatic_hover_positions':nprobe,'pitch_bounds':pitch.json(),
          'probe_metrics':probe_metrics or {},
          'important':'Ledige = bekreftet kjøpbare plasser fra åpne sittefelt. Stengte bortefelt er ikke solgt. Ståplasser ukjent.'}
    (out/'resultat.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    with (out/'felter.csv').open('w',encoding='utf-8-sig',newline='') as f:
        keys=['section','gate','free','capacity','min_free','max_free','availability_state','source','x','y']
        w=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore');w.writeheader();w.writerows(v['fields'])
    with (out/'manglende_felt.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['felt','status']);w.writerows((s,'mangler') for s in missing)
    esc=lambda s:html.escape(str(s))
    rows=''.join(f'<tr><td>{esc(r["section"])}</td><td>{r["free"]}</td><td>{r["capacity"]}</td><td>{esc(r["availability_state"])}</td></tr>' for r in v['fields'])
    missing_html=' '.join(f'<span class="pill">{esc(x)}</span>' for x in missing) or 'Ingen'
    report=f'''<!doctype html><html lang="no"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>RBK Hurtigkart V18</title><style>
    body{{background:#081912;color:#edf7f0;font:15px system-ui;max-width:1000px;margin:auto;padding:25px}}
    .cards{{display:flex;gap:10px;flex-wrap:wrap}}.card{{background:#163922;border-radius:10px;padding:16px;min-width:180px}}.card b{{display:block;font-size:27px}}.pill{{display:inline-block;background:#296240;padding:6px;border-radius:7px;margin:3px}}
    table{{border-collapse:collapse;width:100%}}td,th{{padding:9px;border-bottom:1px solid #39533b;text-align:left}}.warning{{background:#4c3b21;padding:15px;border-radius:8px;color:#ffdfa9}}</style></head><body>
    <h1>RBK Hurtigkart V18 (intern)</h1><p>{esc(url)} · {esc(data['time_utc'])}</p><div class="cards">
    <div class="card"><b>{len(expected&captured)} / {len(expected)}</b>Felt avlest</div><div class="card"><b>{len(locked)}</b>Bekreftet låste bortefelt</div><div class="card"><b>{v['free_seats_confirmed']:,}</b>Ledige i observerte felt</div>
    <div class="card"><b>{len(missing)}</b>Felt som mangler</div><div class="card"><b>{len(v['conflicts'])}</b>Konflikter</div></div>
    <p class="warning">Bekreftet ledige sitteplasser er grunnlaget. Beregnet solgte er IKKE dokumentert salg. Låste bortefelt: {esc(', '.join(sorted(locked)) or 'Ingen')}. Ståplassledighet er ukjent.</p>
    <h2>Manglende felt</h2><p>{missing_html}</p><h2>Registrert</h2><table><tr><th>Felt</th><th>Ledige</th><th>Kapasitet</th><th>Stabilitet</th></tr>{rows}</table></body></html>'''
    (out/'rapport.html').write_text(report,encoding='utf-8')
    return data

def run(args):
    try:from playwright.sync_api import sync_playwright
    except ImportError:print('Playwright mangler. Kjør INSTALLER.bat først.');return 2
    url=args.url or ((ROOT/'fixtures/demo_21_fields.html').resolve().as_uri() if args.demo else input('Lim inn RBK kamp-URL (https://billett.rbk.no/checkout/...): ').strip())
    if not checkout_url(url) and not ((args.local_test or args.demo) and url.startswith('file://')):
        print('Sikkerhet: kun billett.rbk.no/checkout/ er tillatt.');return 2
    try:
        locked=tuple(__import__('match_config').normalize_locked(args.test_locked)) if (args.local_test or args.demo) else load_locked(ROOT/'kampoppsett',url)
    except ValueError as ex:
        print('Ugyldig kampoppsett:',ex);return 2
    print('Bortefelt bekreftet låst for denne kampen:',', '.join(locked) or 'Ingen')
    out=ROOT/'output'/datetime.now().strftime('%Y%m%d_%H%M%S_%f');out.mkdir(parents=True,exist_ok=True)
    learned_path=ROOT/'lagrede_feltposisjoner.json';learned=learned_load(learned_path)
    feedback_path=ROOT/'bekreftede_treff_v16.json';feedback=confirmed_load(feedback_path)
    tried={};probe_log=[];stats={'first':0,'rescue':0,'extra':0,'manual':0,'auto_fields':0,
                     'auto_recovery_fields':0,'bundled_confirmed_fields':len(CONFIRMED_POINTS)}
    counter=Counts();nprobe=0;collector=Collector()
    schedule=ScanSchedule(ROOT/'monitorinnstillinger.json',hours=args.auto_hours,enabled=not args.no_auto)
    registry=EventRegistry(ROOT/'monitor_kamper.json')
    # The user's women-team link is discoverable now, but cannot be scanned
    # using Lerkendal's unverified 60-section profile.
    women_url='https://billett.rbk.no/checkout/6aaceecebfe408c38e1712dd'
    if not registry.get(event_key(women_url)):
        registry.add(women_url,'RBK Kvinner · kartlegging kreves','koteng_arena')
    # Retain both confirmed 2026 Lerkendal fixtures on first installation.
    known_fixtures=[
        ('6a9a7e3f3f93920b289b0675','Rosenborg – Molde'),
        ('6a9a7c2b15599587216e21f3','Rosenborg – Start')]
    for key,title in known_fixtures:
        if not registry.get(key):
            registry.add('https://billett.rbk.no/checkout/'+key,title)
    if checkout_url(url) and not registry.get(event_key(url)):
        registry.add(url,event_labels(url)[0])
    for key,kickoff in [('6a9a7e3f3f93920b289b0675','2026-11-28T18:00'),
                        ('6a9a7c2b15599587216e21f3','2026-11-07T18:00')]:
        item=registry.get(key)
        if item and not item.get('kickoff_at'):
            registry.update(key,kickoff_at=datetime.fromisoformat(kickoff).replace(tzinfo=ZoneInfo('Europe/Oslo')).isoformat())
    last_auto_by_event={}
    if checkout_url(url):
        event=registry.get(event_key(url))
        if event and event['venue']!='lerkendal':
            print('Denne kampen krever en egen verifisert arenaprofil. Ingen Lerkendal-skanning utføres.')
            return 2
        if event and registry.status(event)=='finished':
            print('Kampstart passert. Denne kampen er arkivert og skal ikke skannes.')
            return 2
    if args.no_auto and schedule.enabled:schedule.enable(False)
    expected=set(SEATS);scan_expected=expected-set(locked);cap=dict(SEATS);standing={'SB','ØVRE ØST'};source='stadionreferanse';last=''
    map_verified=False;map_issues={};locked_conflicts={}
    print('\nRBK Billettmonitor V20 | URL:',url)
    print('Automatisk hver',args.auto_hours,'timer:', 'PAA' if schedule.enabled else 'AV')
    print('Rapportmappe:',out)
    with sync_playwright() as pw:
        if args.local_test or args.demo:
            opts={'headless':True}
            if args.chromium_path:opts['executable_path']=args.chromium_path
            elif sys.platform.startswith('win'):opts['channel']='msedge'
            else:opts['executable_path']='/usr/bin/chromium';opts['args']=['--no-sandbox']
            browser=pw.chromium.launch(**opts)
            ctx=browser.new_context(viewport={'width':args.width,'height':args.height});page=ctx.new_page()
            page.set_content(Path(urlparse(url).path).read_text(encoding='utf-8'),wait_until='load')
        else:
            try:
                opened=start_edge(url,args.port,args.edge_path,args.attach_only)
                if opened:print('Eget Edge-vindu åpnet. Vanlig Edge er ikke endret.')
                browser=pw.chromium.connect_over_cdp(f'http://127.0.0.1:{args.port}',timeout=15000)
                ctx=browser.contexts[0]
                page=next((p for p in ctx.pages if p.url.rstrip('/')==url.rstrip('/')),None)
                fresh=page is None
                if fresh:page=ctx.new_page()
                page.on('response',collector.callback)
                if fresh:page.goto(url,wait_until='domcontentloaded',timeout=40000)
                else:
                    print('Fant allerede åpen kampfane. Lesing av kartstruktur krever ny sideinnlasting.')
                    # Usually empty cart in scanner workflow; reload only when empty.
                    try:body=page.locator('body').inner_text(timeout=2000).lower()
                    except Exception:body=''
                    if 'shopping cart is empty' in body or 'handlekurven er tom' in body:
                        page.reload(wait_until='domcontentloaded',timeout=40000)
                    else:print('Fane ikke oppdatert: ukjent/ikke tom handlekurv. Bruker referansefelter.')
                page.bring_to_front()
            except Exception as ex:print('Edge-feil:',str(ex)[:340]);return 2
        for i in range(35):
            if collector.map is not None:break
            page.wait_for_timeout(240)
        if collector.map is not None:
            found,live_cap,found_standing=expected_from_map(collector.map)
            map_verified,map_issues=check_map_against_reference(found,live_cap,locked)
            if found:source='live kartstruktur'
            if found_standing:standing=found_standing
            if not map_verified:
                print('! KARTAVVIK: kartet samsvarer ikke med 60 faste sittefelt:',map_issues)
        else:
            print('! Kunne ikke bekrefte kartstruktur mot live-API. Intern telling mulig, publisering sperres.')
        print(f'Forventer {len(expected)} faste sittefelt; {len(locked)} bekreftet låst; {len(scan_expected)} skal leses. {len(standing)} ståområder separat.')
        if not (args.local_test or args.demo):
            input('Vis hele kartet i Edge som på bildet. Trykk ENTER her når det er klart: ')
        try: match_header = page.locator('body').inner_text(timeout=2500)[:1400]
        except Exception: match_header = ''
        panel_install(page)
        def calibrate():
            image=page.screenshot(full_page=False,timeout=25000)
            (out/'kart_ved_start.png').write_bytes(image)
            w,h=page.evaluate('() => [window.innerWidth,window.innerHeight]')
            pos=locate(image,w,h)
            if pos:return pos
            region,_=choose_map_region(page)
            x1,y1,x2,y2=region
            print('Advarsel: grønn bane ikke identifisert. Bruker reserveplassering.')
            return Pitch(x1+(337-5)/902*(x2-x1),y1+(298-187)/368*(y2-y1),(x2-x1)*243/902,(y2-y1)*157/368)
        pitch=calibrate()
        print('Banen som referanse:',pitch.json())
        dom=dom_labels(page,scan_expected)
        sampler=HoverTransitionSampler(page,read_text,args.hover_ms,{})
        sampler.initialize()
        revision=0
        finalized_revision=-1
        busy=True
        def comparison_history():
            try:history=load_history(ROOT/'historikk',event_key(url))
            except Exception:return []
            return [h for h in history
                    if h.get('locked_fields',[])==list(sorted(locked))
                    and h.get('total')==TOTAL_PLACES
                    and h.get('standing_availability')=='unknown'
                    and isinstance(h.get('available_seated'),int)]
        # Freeze the prior measurement for the entire current run. Publishing
        # the run must not turn its visible +60 change into a false zero.
        baseline_records=comparison_history()
        def metrics():
            return dict(stats,missing_at_save=len(scan_expected-set(counter._groups)),
                        attempted_goal_positions=sum(len(v) for v in tried.values()))
        def update(mode):
            info=counter.export();captured=set(counter._groups)
            remaining=sorted(scan_expected-captured)
            complete=(not remaining and not info['conflicts'] and not locked_conflicts and map_verified)
            comparable=baseline_records
            old=comparable[-1] if comparable else None
            delta=old['available_seated']-info['free_seats_confirmed'] if old and complete else None
            delta_label=('Estimert flere ikke tilgjengelige siden siste godkjente måling' if delta is not None
                         else 'Venter på komplett, sammenlignbar måling')
            title,match_date=(event_labels(url,match_header) if checkout_url(url) else ('RBK Demokamp', 'Syntetiske testdata'))
            chart_records=list(comparable)
            if complete:
                chart_records.append({'time_utc':datetime.now(timezone.utc).isoformat(timespec='seconds'),
                    'total':TOTAL_PLACES,'available_seated':info['free_seats_confirmed'],
                    'locked_fields':list(sorted(locked)),'standing_availability':'unknown'})
            title,match_date=(event_labels(url,match_header) if checkout_url(url) else ('RBK Demokamp','Syntetiske testdata'))
            projection=forecast(chart_records,match_date,locked)
            chart=[x['free'] for x in projection['points'][-30:]]
            data={'mode':mode,'found':len(expected&captured),'covered':len((expected&captured)|set(locked)),
                  'total':len(expected),'locked':len(locked),'locked_names':list(sorted(locked)),
                  'missing':remaining,'free':info['free_seats_confirmed'],
                  'estimated':TOTAL_PLACES-info['free_seats_confirmed'],'complete':complete,
                  'conflicts':len(info['conflicts'])+len(locked_conflicts),'last':last,
                  'title':title,'match_date':match_date,'event_key':event_key(url) if checkout_url(url) else 'syntetisk',
                  'delta':delta,'delta_label':delta_label,'chart':chart,
                  'forecast':{k:projection.get(k) for k in ('state','value','low','high','daily_change','message','hours_until','kickoff_utc')},
                  'chart_points':projection['points'][-30:],
                  'auto_enabled':schedule.enabled,'auto_remaining':schedule.seconds_remaining(),
                  'clock':datetime.now().strftime('%H:%M:%S'),'busy':busy,
                  'registered_events':[{**e,'status':registry.status(e)} for e in registry.items]}
            panel_show(page,data)
            return data
        def register(hit,manual=None,goal=None,phase=None):
            nonlocal last,revision
            if hit.section not in expected:return False
            if hit.section in locked:
                if hit.free>0:
                    locked_conflicts[hit.section]=[{'reason':'Oppgitt låst, men viser ledige billetter','free':hit.free}]
                    print('! BORTEFELT-MOTSIGELSE:',hit.section,hit.free,'ledige. Publisering stoppes.')
                return False
            if cap.get(hit.section) and hit.capacity!=cap[hit.section]:
                print('! Kapasitet avviker fra kartstruktur:',hit.section,hit.capacity,cap[hit.section]);return False
            state=counter.add(hit)
            # Save a position only when the tooltip actually matches the hover goal.
            # A valid but unexpected popup can still be recorded as a separate field.
            if not manual and goal==hit.section and pitch and hit.x>=0:
                record_verified(feedback_path,feedback,hit.section,(hit.x,hit.y),pitch,'automatic')
            if state not in ('new','variable','conflict'):return False
            revision+=1
            last=f'{hit.section}: {hit.free}/{hit.capacity} ({"manuelt" if manual else "automatisk"})'
            print(('  +' if state=='new' else '  ~' if state=='variable' else '  !'),last,flush=True)
            if state=='new':
                if manual:stats['manual']+=1
                else:
                    stats['auto_fields']+=1
                    if phase=='rescue' or phase=='extra':stats['auto_recovery_fields']+=1
            update('Manuell komplettering' if manual else 'Automatisk skanning')
            save_reports(out,counter,expected,cap,standing,url,source,nprobe,'live',pitch,metrics(),locked,map_verified,map_issues,locked_conflicts)
            if manual and pitch and manual['x']>=0:
                rx,ry=to_reference((manual['x'],manual['y']),pitch)
                if -500<rx<1400 and -500<ry<1200:
                    learned[hit.section]=[rx,ry]
                    learned_save(learned_path,learned)
            return True
        def targets(names,deep=False):
            return {name:field_candidates(name,pitch,learned,feedback,CONFIRMED_POINTS,
                         dom,KNOWN,OLD,deep) for name in sorted(names)}
        def probe_phase(phase,limit):
            nonlocal nprobe
            wanted=scan_expected-set(counter._groups)
            options=targets(wanted,deep=phase=='extra')
            if phase=='first':
                queue=((name,pts[0][1],pts[0][2],pts[0][0]) for name,pts in options.items() if pts)
            else:
                queue=round_robin_recovery(options,tried,
                              per_field_limit=args.deep_retries if phase=='extra' else args.retry_per_field)
            start=monotonic();attempts=0
            for goal,x,y,origin in queue:
                if attempts>=limit:break
                if goal in counter._groups:continue
                if (x,y) in tried.get(goal,set()):continue
                w,h=page.evaluate('() => [window.innerWidth,window.innerHeight]')
                if not (3<x<w-3 and 3<y<h-3):continue
                tried.setdefault(goal,set()).add((x,y))
                attempts+=1;nprobe+=1;stats[phase]+=1
                try:
                    # The transition sampler rejects a stale tooltip left on the
                    # page from the previous hover. No blind text-only fallback.
                    hits=sampler.hover(x,y,'v16-'+phase)
                    probe_log.append({'goal':goal,'phase':phase,'x':x,'y':y,
                                      'origin':origin,'observed':sorted({h.section for h in hits})})
                    for hit in hits:register(hit,goal=goal,phase=phase)
                except Exception as ex:
                    if args.debug:print('Punktfeil:',goal,origin,type(ex).__name__,str(ex)[:100])
                if attempts%30==0:
                    print(f'... {attempts} punkt i fase {phase} / {len(expected&set(counter._groups))} felt funnet')
            print(f'Fase {phase}: {attempts} punkter, {len(expected&set(counter._groups))}/{len(expected)} felt. Tid: {round(monotonic()-start,1)} s')
        def automated_cycle():
            nonlocal busy
            busy=True
            update('Leser kartet automatisk · la kartet være synlig')
            if not args.manual_only:
                probe_phase('first',max(0,args.max_points-nprobe))
                if not args.first_only and scan_expected-set(counter._groups):
                    update('Prøver alternative punkter i redningsrunde')
                    print('Automatisk redningsrunde for:',', '.join(sorted(scan_expected-set(counter._groups))))
                    probe_phase('rescue',max(0,args.max_points-nprobe))
                if args.extra and scan_expected-set(counter._groups):
                    probe_phase('extra',max(0,args.max_points-nprobe))
            (out/'treffpunkt_diagnose_v16.json').write_text(json.dumps({'version':16,'attempts':probe_log},
                                ensure_ascii=False,indent=2),encoding='utf-8')
            busy=False
            now=update('Klar · Lagre eller kjør ny sjekk')
            print('Mangler:',', '.join(now['missing']) or 'Ingen')
            save_reports(out,counter,expected,cap,standing,url,source,nprobe,'after-auto',pitch,metrics(),locked,map_verified,map_issues,locked_conflicts)
            if not (args.demo or args.local_test):
                finalize_cycle()  # Always store complete checks; incomplete ones remain internal.
            schedule.scan_finished()
            update('Klar · Automatisk kontroll er ' + ('på' if schedule.enabled else 'av'))
            if args.demo:
                page.screenshot(path=str(out/'demo_med_livepanel.png'),full_page=False)

        def finalize_cycle():
            nonlocal finalized_revision
            if finalized_revision==revision:
                return False
            (out/'treffpunkt_diagnose_v16.json').write_text(json.dumps({'version':16,'attempts':probe_log},
                                 ensure_ascii=False,indent=2),encoding='utf-8')
            final=save_reports(out,counter,expected,cap,standing,url,source,nprobe,'final',pitch,metrics(),locked,map_verified,map_issues,locked_conflicts)
            finalized_revision=revision
            # A scan may have started just before kickoff. Archive its local
            # diagnostics, but never upload a post-kickoff seat count.
            event=registry.get(event_key(url)) if checkout_url(url) else None
            if event and registry.status(event)=='finished':
                print('Kamp startet: ingen ny publisering etter avspark')
                update('Kampstart passert · historikken er avsluttet')
                return False
            print('Måling:',final['captured_fields'],'avlest +',len(locked),'låst av 60. Ledige:',final['free_confirmed_fields'])
            try:
                post=publish(final,out,ROOT/'historikk',browser=browser,header_text=match_header)
                if post['published']:
                    all_history=load_history(ROOT/'historikk',event_key(url))
                    chart_path=save_chart(out,all_history,post['record']['title'],post['record']['match_date'],event_key(url),locked)
                    # Persist a stable per-event latest graph as well as per-run output.
                    graph_dir=ROOT/'historikk'/'grafer'/event_key(url)
                    save_chart(graph_dir,all_history,post['record']['title'],post['record']['match_date'],event_key(url),locked)
                    print('Statusbilder, billettgraf og historikk lagret:',out)
                    try:
                        from sync_ministaut import upload as ministaut_upload
                        ministaut_upload(out/'resultat.json')
                        print('Ministaut: godkjent maaling lastet opp til GoalPulz Supabase')
                    except Exception as sync_error:
                        print('Ministaut: opplasting utsatt/feilet:',str(sync_error)[:250])

                    update('Lagret · Graf oppdatert · Ny sjekk om 1 time')
                else:
                    print('Intern rapport lagret. Publiseringskontroll:',post['reason'])
                    update('Rapport lagret · '+post['reason'][:80])
            except Exception as ex:
                print('Rapport lagret, feil ved publisering:',type(ex).__name__,str(ex)[:200])
                update('Intern rapport lagret · Kunne ikke generere post')
            return True

        def start_next_cycle(next_url=None, new_locked=None):
            """Reuse existing Playwright/Edge connection; never reuse seat counts."""
            nonlocal url,locked,scan_expected,out,collector,source,map_verified,map_issues,standing
            nonlocal counter,nprobe,tried,probe_log,stats,locked_conflicts,last,pitch,dom,sampler
            nonlocal match_header,revision,finalized_revision,busy,page,baseline_records
            destination=next_url or url
            if not checkout_url(destination) and not ((args.local_test or args.demo) and destination.startswith('file://')):
                print('Avvist: ugyldig kampadresse')
                update('Ugyldig RBK checkout-adresse')
                return False
            try:
                if checkout_url(destination): event_key(destination)
                requested_locked=tuple(normalize_locked(new_locked)) if new_locked is not None else (load_locked(ROOT/'kampoppsett',destination) if checkout_url(destination) else tuple(normalize_locked(args.test_locked)))
            except ValueError as ex:
                update('Ugyldig kampoppsett: '+str(ex)[:75]);return False
            print('Ny måling startes:',destination,'| Låste:', ','.join(requested_locked) or 'ingen')
            # Every repeat MUST fetch a fresh live seatmap; stale tooltips and
            # previous count objects are never carried into a new measurement.
            try:
                if args.local_test or args.demo:
                    # Fresh synthetic page context avoids duplicate const bindings
                    # and file:// navigation, which may be blocked by Chromium.
                    oldpage=page
                    page=ctx.new_page()
                    page.set_content(Path(urlparse(destination).path).read_text(encoding='utf-8'),wait_until='load')
                    oldpage.close()
                else:
                    collector.map=None
                    if next_url is not None and destination.rstrip('/')!=page.url.rstrip('/'):
                        page.goto(destination,wait_until='domcontentloaded',timeout=40000)
                    else:
                        page.reload(wait_until='domcontentloaded',timeout=40000)
                page.bring_to_front()
            except Exception as ex:
                print('Kunne ikke oppdatere siden:',type(ex).__name__,str(ex)[:220]);
                try:panel_install(page);update('Ny sjekk mislyktes · prøv igjen')
                except Exception:pass
                return False
            url=destination
            locked=requested_locked
            scan_expected=expected-set(locked)
            map_verified=False;map_issues={};source='stadionreferanse';standing={'SB','ØVRE ØST'}
            if not (args.local_test or args.demo):
                for _ in range(55):
                    if collector.map is not None:break
                    page.wait_for_timeout(210)
                if collector.map is not None:
                    names,live_cap,found_standing=expected_from_map(collector.map)
                    map_verified,map_issues=check_map_against_reference(names,live_cap,locked)
                    if names:source='live kartstruktur'
                    if found_standing:standing=found_standing
                if not map_verified:
                    print('! Live kartstruktur ikke verifisert ved ny kjøring:',map_issues)
            try:match_header=page.locator('body').inner_text(timeout=2500)[:1400]
            except Exception:match_header=''
            out=ROOT/'output'/datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            out.mkdir(parents=True,exist_ok=True)
            counter=Counts();nprobe=0;tried={};probe_log=[];last=''
            stats={'first':0,'rescue':0,'extra':0,'manual':0,'auto_fields':0,
                   'auto_recovery_fields':0,'bundled_confirmed_fields':len(CONFIRMED_POINTS)}
            locked_conflicts={};revision=0;finalized_revision=-1;busy=True
            baseline_records=comparison_history()
            panel_install(page)
            pitch=calibrate()
            dom=dom_labels(page,scan_expected)
            sampler=HoverTransitionSampler(page,read_text,args.hover_ms,{})
            sampler.initialize()
            automated_cycle()
            return True

        automated_cycle()
        print('Bruk panelet: «Ny sjekk» kjører en ny telling i samme Edge-sesjon.')
        print('«Lagre + publiser» oppretter en ny rapport uten å avslutte.')
        print('«Avslutt sesjon» avslutter og lagrer den siste målingen.')
        if not (args.local_test or args.demo):
            # The V19 background stdin reader could terminate the live control
            # loop on an extra ENTER or EOF. Only panel Stop / Ctrl+C should stop.
            last_pointer=mouse_location(page)['t'];prior_signature=None;stable=0
            deadline=monotonic()+args.manual_seconds if args.manual_seconds>0 else float('inf')
            while monotonic()<deadline:
                try:
                    command=panel_command(page)
                    if command:
                        print('Kontrollpanel:',command.split(':',1)[0],flush=True)
                    if command=='stop':break
                    elif command in ('save','save_final'):
                        finalize_cycle()
                    elif command=='new_scan':
                        update('Lagrer måling · forbereder ny skanning …')
                        finalize_cycle()
                        if start_next_cycle():
                            deadline=monotonic()+args.manual_seconds if args.manual_seconds>0 else float('inf')
                            prior_signature=None;stable=0;last_pointer=mouse_location(page)['t']
                        continue
                    elif command.startswith('register:'):
                        try:
                            destination,venue=command.split(':',1)[1].rsplit('|',1)
                            registry.add(destination,venue=venue)
                            update('Kamp lagret · registrer avspark for automatisk telling')
                        except ValueError as ex:update('Kunne ikke lagre kamp: '+str(ex)[:80])
                        continue
                    elif command.startswith('kickoff:'):
                        try:
                            key,local=command.split(':',1)[1].split('|',1)
                            dt=datetime.fromisoformat(local).replace(tzinfo=ZoneInfo('Europe/Oslo'))
                            registry.update(key,kickoff_at=dt.isoformat())
                            update('Kampstart lagret')
                        except (ValueError,IndexError) as ex:update('Feil kampstart: '+str(ex)[:70])
                        continue
                    elif command.startswith('select_registered:'):
                        key=command.split(':',1)[1]
                        entry=registry.get(key)
                        if not entry:
                            update('Kamp finnes ikke i listen');continue
                        state=registry.status(entry)
                        if state=='awaiting_kickoff':
                            update('Mangler kampstart · velg kampen og lagre avspark i panelet');continue
                        if state=='finished':
                            update('Kampstart er passert · sjekk eller korriger dato og klokkeslett');continue
                        if state=='awaiting_map':
                            update('Koteng Arena avventer kontrollert skannerprofil');continue
                        if entry['venue']!='lerkendal':
                            update('Koteng må kartlegges før skanning kan aktiveres');continue
                        finalize_cycle()
                        if start_next_cycle(next_url=entry['url']):
                            update('Kampbytte utført · '+entry['title'])
                            deadline=monotonic()+args.manual_seconds if args.manual_seconds>0 else float('inf')
                            prior_signature=None;stable=0;last_pointer=mouse_location(page)['t']
                        continue
                    elif command.startswith('switch:'):
                        destination=command.split(':',1)[1]
                        update('Lagrer måling · åpner ny kamp …')
                        if checkout_url(destination):
                            candidate=registry.get(event_key(destination))
                            if candidate and registry.status(candidate)!='scheduled':
                                update('Lagre kampstart før skanning');continue
                            if candidate and candidate['venue']!='lerkendal':
                                update('Koteng-kamp lagret, men krever egen skannerprofil');continue
                            # A new URL becomes a reusable saved fixture, not a one-off switch.
                            try:registry.add(destination)
                            except ValueError:pass
                            finalize_cycle()
                            if start_next_cycle(next_url=destination):
                                deadline=monotonic()+args.manual_seconds if args.manual_seconds>0 else float('inf')
                                prior_signature=None;stable=0;last_pointer=mouse_location(page)['t']
                        else:update('Ugyldig URL · bare billett.rbk.no/checkout/…')
                        continue
                    elif command.startswith('locked:'):
                        raw=command.split(':',1)[1]
                        update('Lagrer måling · oppdaterer bortefelt …')
                        try:
                            new_locked=normalize_locked(raw)
                            finalize_cycle()
                            save_locked(ROOT/'kampoppsett',url,new_locked,confirmed=True)
                            if start_next_cycle(new_locked=new_locked):
                                deadline=monotonic()+args.manual_seconds if args.manual_seconds>0 else float('inf')
                                prior_signature=None;stable=0;last_pointer=mouse_location(page)['t']
                        except ValueError as ex:
                            print('Bortefelt kunne ikke lagres:',ex)
                            update('Ugyldig feltoppsett: '+str(ex)[:70])
                        continue
                    elif command=='auto_toggle':
                        schedule.enable(not schedule.enabled)
                        update('Automatisk sjekk: ' + ('på · hver time' if schedule.enabled else 'av'))
                    elif command=='open_chart':
                        graph=ROOT/'historikk'/'grafer'/event_key(url)/'billettutvikling.html'
                        if graph.is_file():
                            if sys.platform.startswith('win'):os.startfile(str(graph))
                            update('Historikkgraf åpnet: '+graph.name)
                        else:update('Ingen godkjent graf ennå · lagre en komplett måling')
                    elif command=='open_output':
                        print('Resultatmappe:',out)
                        if sys.platform.startswith('win'):os.startfile(str(out))
                        update('Resultatmappe: '+out.name)
                    elif command=='open_share':
                        finalize_cycle()
                        candidate=out/'delbar_status_4x5.png'
                        if candidate.is_file():
                            if sys.platform.startswith('win'):os.startfile(str(candidate))
                            update('Statusbildet er klart · '+candidate.name)
                        else:update('Statusbilde ikke tilgjengelig · se kvalitetskontroll')
                    elif command=='recalibrate':
                        pitch=calibrate();dom=dom_labels(page,scan_expected);tried.clear();sampler.initialize()
                        update('Kartkoordinater oppdatert')
                    elif command=='retry':
                        sampler.initialize();tried.clear();busy=True
                        probe_phase('rescue',min(180,max(0,args.max_points-nprobe)))
                        busy=False;update('Klar · manglende felt forsøkt igjen')
                    elif command.startswith('field:'):
                        name=command.split(':',1)[1]
                        if name in scan_expected-set(counter._groups):
                            for origin,x,y in targets({name}).get(name,[])[:2]:
                                nprobe+=1
                                for hit in sampler.hover(x,y,'v16-clicked-missing'):
                                    register(hit,goal=name,phase='rescue')
                    if schedule.due():
                        # Each configured match is independent; finished events are archived.
                        active=registry.eligible()
                        tick=monotonic()
                        due=[e for e in active if tick-last_auto_by_event.get(e['key'],-1e12)>=schedule.seconds]
                        due.sort(key=lambda e:last_auto_by_event.get(e['key'],-1e12))
                        target=due[0] if due else None
                        if target:
                            current_key=event_key(url) if checkout_url(url) else ''
                            current_entry=registry.get(current_key)
                            if current_entry and registry.status(current_entry)=='scheduled':
                                finalize_cycle()
                                last_auto_by_event[current_key]=monotonic()
                            if start_next_cycle(next_url=target['url']):
                                last_auto_by_event[target['key']]=monotonic()
                                deadline=monotonic()+args.manual_seconds if args.manual_seconds>0 else float('inf')
                                prior_signature=None;stable=0;last_pointer=mouse_location(page)['t']
                            else:schedule.postpone_after_error()
                        elif not active:
                            update('Ingen aktive kamper · avventer nye')
                        schedule.scan_finished()
                        # Drain other due fixtures promptly, without overlapping scans.
                        if registry.eligible() and any(
                            monotonic()-last_auto_by_event.get(e['key'],-1e12)>=schedule.seconds
                            for e in registry.eligible()
                        ):
                            schedule.next_due=monotonic()+8
                        continue
                    mouse=mouse_location(page)
                    hits=parse_visible_texts(read_text(page),'v16-manual',mouse['x'],mouse['y'])
                    signature=tuple(sorted((x.section,x.free,x.capacity) for x in hits))
                    if signature and signature==prior_signature:stable+=1
                    else:prior_signature=signature;stable=1
                    if stable>=2 and mouse['t']>last_pointer:
                        for hit in hits:
                            x,y=mouse['x'],mouse['y']
                            on_map=pitch.x-1.6*pitch.w<=x<=pitch.x+2.5*pitch.w and pitch.y-pitch.h<=y<=pitch.y+2*pitch.h
                            if on_map and hit.section in scan_expected and (hit.section not in counter._groups or hit.free not in
                                {v['free'] for v in counter._groups[hit.section]}):
                                register(hit,manual=mouse);last_pointer=mouse['t']
                    page.wait_for_timeout(170)
                except KeyboardInterrupt:break
                except Exception as ex:
                    if args.debug:print('Panelvarsel:',type(ex).__name__,str(ex)[:150])
                    try:page.wait_for_timeout(250)
                    except Exception:break
        if args.local_test and args.test_cycles>1:
            for _ in range(args.test_cycles-1):
                finalize_cycle()
                start_next_cycle()
        finalize_cycle()
        print('Siste resultatmappe:',out)
        print('Sesjonen er avsluttet. Edge forblir åpen; ingen billetter ble valgt.')
        if args.local_test or args.demo:ctx.close();browser.close()
    return 0

def main():
    p=argparse.ArgumentParser(description='RBK Billettmonitor V20 – URL, ett punkt/felt, live mangelliste, sosial status')
    p.add_argument('--url',default='');p.add_argument('--port',type=int,default=9222)
    p.add_argument('--auto-hours',type=float,default=1.0,help='Timer mellom automatiske sjekker (standard 1)')
    p.add_argument('--no-auto',action='store_true',help='Avslå automatiske sjekker til slått på i panelet')
    p.add_argument('--edge-path',default=None);p.add_argument('--attach-only',action='store_true')
    p.add_argument('--manual-only',action='store_true');p.add_argument('--extra',action='store_true')
    p.add_argument('--first-only',action='store_true',help='Skip the default automatic recovery pass')
    p.add_argument('--retry-per-field',type=int,default=10)
    p.add_argument('--deep-retries',type=int,default=20)
    p.add_argument('--max-points',type=int,default=350);p.add_argument('--hover-ms',type=int,default=80)
    p.add_argument('--manual-seconds',type=int,default=0);p.add_argument('--debug',action='store_true')
    p.add_argument('--local-test',action='store_true');p.add_argument('--demo',action='store_true');p.add_argument('--chromium-path',default='')
    p.add_argument('--test-locked',default='',help='ONLY synthetic --local-test: emulate confirmed locked sections')
    p.add_argument('--test-cycles',type=int,default=1,help='ONLY --local-test: repeated scans in one browser instance')
    p.add_argument('--width',type=int,default=1360);p.add_argument('--height',type=int,default=850)
    args=p.parse_args()
    if not (0.05 <= args.auto_hours <= 168):p.error('--auto-hours må være mellom 0.05 og 168')
    return run(args)

if __name__=='__main__':raise SystemExit(main())