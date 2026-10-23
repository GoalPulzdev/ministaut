"""Read-only audit report for observed field availability, not ticket sales."""
from __future__ import annotations
import csv
import html
import json
from pathlib import Path
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parent


def _reference():
    target=ROOT/'video_22_10_felter.csv'
    if not target.exists():return set()
    with target.open(encoding='utf-8-sig',newline='') as file:
        return {r['section'].strip().upper() for r in csv.DictReader(file) if r.get('section')}


def write_report(counts,destination:Path,url:str,mode:str,meta:dict)->Path:
    destination.mkdir(parents=True,exist_ok=True)
    result=counts.export()
    expected=_reference()
    captured={f['section'] for f in result['fields']}|set(result['conflicts'])
    missing=sorted(expected-captured)
    result.update({
        'event':'Rosenborg - Molde | 28.11.2026 kl. 18:00',
        'url':url,'scanned_utc':meta.get('source_scanned_utc') or datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'mode':mode,'diagnostics':meta,
        'reference_field_count':len(expected),'covered_reference_fields':len(expected)-len(missing),
        'missing_reference_fields':missing,
        'coverage_complete': False, # video did not cover two known labels or GA availability fully.
    })
    (destination/'resultat.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    columns=['section','gate','free','min_free','max_free','capacity','availability_state','variants','source','x','y']
    with (destination/'felter.csv').open('w',newline='',encoding='utf-8-sig') as file:
        writer=csv.DictWriter(file,fieldnames=columns,extrasaction='ignore');writer.writeheader()
        writer.writerows(result['fields'])
    with (destination/'konflikter.json').open('w',encoding='utf-8') as file:
        json.dump(result['conflicts'],file,ensure_ascii=False,indent=2)
    with (destination/'api_struktur.json').open('w',encoding='utf-8') as file:
        json.dump(meta.get('public_response_schemas',{}),file,ensure_ascii=False,indent=2)
    with (destination/'manglende_felt.csv').open('w',newline='',encoding='utf-8-sig') as file:
        writer=csv.writer(file);writer.writerow(['section','status','reference'])
        for section in missing:writer.writerow([section,'ikke_fanget','video_2026-10-22'])

    E=lambda text:html.escape(str(text))
    show_range=result['free_seats_min']!=result['free_seats_max']
    free_text=(f"{result['free_seats_min']:,}–{result['free_seats_max']:,}" if show_range
               else f"{result['free_seats_confirmed']:,}")
    rows=[]
    for field in result['fields']:
        free=field['free'];capacity=field['capacity'];percent=100*free/capacity
        variable=field['availability_state']=='variable'
        status='<span class="pill alt">Varierer</span>' if variable else '<span class="pill">Stabil</span>'
        count=(f"{field['min_free']}–{field['max_free']}" if variable else str(free))
        rows.append(f'<tr><td><b>{E(field["section"])}</b></td><td>{E(field["gate"]) or "–"}</td>'
                    f'<td class="num">{E(count)}</td><td class="num">{capacity:,}</td><td>{status}</td>'
                    f'<td><div class="meter"><span style="width:{percent:.1f}%"></span></div></td></tr>')
    rows_html='\n'.join(rows) or '<tr><td colspan="6" class="muted">Ingen felt er verifisert i denne økten.</td></tr>'
    conflict_rows=[]
    for field,observations in sorted(result['conflicts'].items()):
        readings=', '.join(f'{x["free"]}/{x["capacity"]}' for x in observations)
        conflict_rows.append(f'<tr><td>{E(field)}</td><td>{E(readings)}</td></tr>')
    issues=''
    if conflict_rows:
        issues='<section><h2>Større konflikter som må undersøkes</h2><div class="scroll"><table><tbody>'+''.join(conflict_rows)+'</tbody></table></div></section>'
    missing_label=', '.join(missing) if missing else 'Ingen av de 59 videoregistrerte feltene'
    range_note='Felt med små variasjoner vises med minste og største observerte verdi.' if result['variable_count'] else 'Alle registrerte felt hadde stabile verdier under denne økten.'
    pct=round((len(expected)-len(missing))*100/len(expected)) if expected else 0
    reanalysis_note = ('<div class="notice"><b>Etteranalyse av tidligere kjøring – ikke en ny live-avlesning.</b>\n'
        'Feltverdiene kommer fra V3 og er ikke bekreftet på nytt med V4 sin popup-kontroll.</div>'
        if mode=='v3-reanalyse' else '')
    data=f'''<!DOCTYPE html><html lang="no"><head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>RBK–Molde · Tilgjengelighet V5</title><style>
:root{{font-family:Inter,system-ui,-apple-system,Segoe UI,Arial,sans-serif;background:#08120f;color:#edf6f2;color-scheme:dark}}
*{{box-sizing:border-box}}body{{max-width:1180px;margin:auto;padding:35px 22px}}
h1{{font-size:clamp(1.8rem,4vw,3.25rem);letter-spacing:-.05em;margin:8px 0}}h2{{font-size:1.1rem;margin:0;padding:16px 20px;border-bottom:1px solid #254238}}
small,.muted{{color:#a5bdb2}}.eyebrow{{color:#55e4a2;font-size:.77rem;font-weight:800;text-transform:uppercase;letter-spacing:.14em}}
header{{display:flex;justify-content:space-between;flex-wrap:wrap;gap:15px}}.headmeta{{text-align:right;color:#afc2b8;font-size:.85rem}}
.cards{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:15px;margin:28px 0}}
.card,section{{border:1px solid #244136;border-radius:17px;background:#10231c;overflow:hidden}}
.card{{padding:22px}}.card strong{{display:block;font-size:clamp(1.5rem,3.2vw,2.7rem);letter-spacing:-.06em;font-variant-numeric:tabular-nums}}
.card span{{font-size:.83rem;color:#a5c4b4}}.highlight{{color:#62e9ae}}
.progress{{height:10px;background:#2c463a;border-radius:20px;overflow:hidden;margin:18px 0 8px}}.progress>span{{display:block;background:#38d995;height:100%}}
.notice{{background:#242218;border-left:3px solid #e5bc6c;padding:17px;line-height:1.6;margin:20px 0;border-radius:8px}}
section{{margin:22px 0}}.sectionbody{{padding:20px;line-height:1.7}}.scroll{{overflow:auto}}table{{width:100%;border-collapse:collapse;min-width:650px}}
th,td{{padding:12px 18px;border-bottom:1px solid #25392f;text-align:left;font-size:.91rem}}th{{font-size:.75rem;text-transform:uppercase;color:#9eb6aa}}tr:last-child td{{border:none}}.num{{text-align:right;font-variant-numeric:tabular-nums}}
.pill{{font-size:.69rem;border:1px solid #2e7651;border-radius:100px;padding:3px 9px;color:#75ecb2}}.pill.alt{{color:#e8ce87;border-color:#987334}}
.meter{{width:100px;height:7px;background:#2e483a;border-radius:10px;overflow:hidden}}.meter span{{display:block;background:#41d8a0;height:100%}}
footer{{color:#8ca79a;font-size:.86rem;line-height:1.7;padding-bottom:25px}}a{{color:#66e8ad}}
@media(max-width:700px){{body{{padding:23px 14px}}.cards{{grid-template-columns:1fr}}.headmeta{{text-align:left}}}}
</style></head><body>
<header><div><div class="eyebrow">Lerkendal · 28. november 2026</div><h1>Rosenborg – Molde</h1>
<div class="muted">Kartlegging av ledige seter · delvis opptelling</div></div>
<div class="headmeta">Avlest: {E(result['scanned_utc'])} UTC<br/>Modus: {E(mode)}<br/>Ingen reservasjoner</div></header>
{reanalysis_note}
<div class="cards"><div class="card"><strong class="highlight">{E(free_text)}</strong><span>Ledige i godkjente felt, intervall</span></div>
<div class="card"><strong>{result['field_count']}</strong><span>Felt med godkjente observasjoner</span></div>
<div class="card"><strong>{len(expected)-len(missing)} / {len(expected)}</strong><span>Felt funnet fra videoreferansen</span></div></div>
<div class="progress"><span style="width:{pct}%"></span></div>
<small>Referansedekning {pct} % gjelder bare feltene registrert i videoen, ikke hele Lerkendal.</small>
<div class="notice"><b>Dette er ikke solgte billetter eller stadionbelegg.</b> Ukjente, sperrede, reserverte,
sesongkort- og ståfelt kan mangle. Kapasitet minus ledige er ikke et offisielt salgstall.
{E(range_note)} De {result['conflict_count']} større konfliktene er holdt utenfor tallintervallet.</div>
<section><h2>Manglende felter i forhold til videoen ({len(missing)})</h2>
<div class="sectionbody"><b>{E(missing_label)}</b><div class="muted">Disse er ukjente, ikke registrert med null.
Ved behov kan de undersøkes i assistert modus. Videoen manglet dessuten lesbare verdier for SB og B.</div></div></section>
<section><h2>Felt for felt</h2><div class="scroll"><table><thead><tr><th>Felt</th><th>Inngang</th><th class="num">Ledige</th><th class="num">Kapasitet</th><th>Observasjon</th><th>Ledig %</th></tr></thead><tbody>{rows_html}</tbody></table></div></section>
{issues}
<footer>Observasjon fra <a href="{E(url)}" target="_blank" rel="noreferrer">RBKs offentlige billettkart</a>.
Følg `resultat.json` for diagnostikk, `api_struktur.json` for strukturen i offentlige datakall,
`manglende_felt.csv` for mangler og `felter.csv` for dataene. Ingen kjøp eller reservasjoner ble foretatt av programmet.</footer>
</body></html>'''
    path=destination/'rapport.html'
    path.write_text(data,encoding='utf-8')
    return path