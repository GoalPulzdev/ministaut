import 'jsr:@supabase/functions-js/edge-runtime.d.ts';
import { createClient } from 'npm:@supabase/supabase-js@2.95.0';
const admin=createClient(Deno.env.get('SUPABASE_URL')!,Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!,{auth:{persistSession:false}});
const capacities:Record<string,number>={'VIP':71,'FELT-1':49,'FELT-2':160,'FELT-3':120,'FELT-4':152,'FELT-5':49};
const EVENT='6aaceecebfe408c38e1712dd';
const json=(status:number,value:unknown)=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json','Cache-Control':'no-store'}});
const deny=(reason:string)=>json(422,{error:reason});
Deno.serve(async req=>{
  if(req.method!=='POST')return json(405,{error:'POST required'});
  const token=req.headers.get('x-ministaut-token')||'';
  if(!(/^[a-f0-9]{64}$/.test(token)||/^[A-Za-z0-9_-]{30,200}$/.test(token)))return json(401,{error:'Unauthorized'});
  const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(token)))).map(v=>v.toString(16).padStart(2,'0')).join('');
  const {data:identity,error:authError}=await admin.from('ministaut_scanner_tokens').select('token_name').eq('token_hash',digest).eq('enabled',true).maybeSingle();
  if(authError||!identity)return json(401,{error:'Unauthorized'});
  const p=await req.json().catch(()=>null);
  if(!p||typeof p!=='object')return deny('Invalid JSON');
  if(p.event_key!==EVENT||p.venue_id!=='koteng_arena'||p.profile_version!=='koteng-v1.8-geometry-locked-20261026')return deny('Unknown event, stadium or locked profile');
  if(p.quality_status!=='LOCKED_LOCAL_VERIFIED'||p.two_read_coverage_complete!==true||p.local_seated_coverage_verified!==true||p.lock_integrity_verified!==true)return deny('Unverified local scan');
  if(p.public_approved!==false||p.reading_status!=='pending')return deny('Only pending scans accepted');
  if(!/^[A-Za-z0-9_.:-]{8,160}$/.test(String(p.source_run_id||'')))return deny('Invalid run ID');
  const observed=Date.parse(String(p.observed_at||''));
  if(!Number.isFinite(observed)||observed>Date.now()+300000||observed<Date.now()-30*86400000)return deny('Invalid observation time');
  if(!Array.isArray(p.sections)||p.sections.length!==6||!Array.isArray(p.locked_fields)||p.locked_fields.length!==0)return deny('Invalid six-field inventory');
  const seen=new Set<string>();let total=0;
  for(const s of p.sections){
    if(!s||typeof s.section!=='string'||!Object.prototype.hasOwnProperty.call(capacities,s.section)||seen.has(s.section))return deny('Unknown or duplicate section');
    if(!Number.isInteger(s.free)||!Number.isInteger(s.capacity)||s.capacity!==capacities[s.section]||s.free<0||s.free>s.capacity||s.confirmed_passes<2||s.min_free!==s.free||s.max_free!==s.free)return deny('Bad section/unstable observation');
    seen.add(s.section);total+=s.free;
  }
  if(total!==p.available_seated||p.reference_capacity_seated!==601)return deny('Total mismatch');
  const {data:match,error:matchErr}=await admin.from('ministaut_koteng_matches').select('id,is_published').eq('event_key',EVENT).single();
  if(matchErr||!match||match.is_published!==true)return json(503,{error:'Event not published'});
  const {data:existing}=await admin.from('ministaut_koteng_scans').select('id,available_seated,observed_at').eq('match_id',match.id).eq('source_run_id',p.source_run_id).maybeSingle();
  if(existing){
    if(existing.available_seated!==total||Date.parse(existing.observed_at)!==observed)return deny('Run ID collision');
    return json(200,{ok:true,scan_id:existing.id,duplicate:true,status:'observed'});
  }
  const {data:scan,error:scanErr}=await admin.from('ministaut_koteng_scans').insert({
    match_id:match.id,source_run_id:p.source_run_id,observed_at:new Date(observed).toISOString(),
    available_seated:total,counted_sections:6,locked_fields:[],reading_status:'observed',
    standing_status:'unknown',ticket_category:String(p.ticket_category||'ukjent').slice(0,60),
    ticket_category_verified:false,inventory_verified:false
  }).select('id').single();
  if(scanErr||!scan)return json(500,{error:'Could not save scan'});
  const {error:detailErr}=await admin.from('ministaut_koteng_section_measurements').insert(p.sections.map((s:{section:string,free:number,capacity:number})=>({scan_id:scan.id,section_code:s.section,free:s.free,capacity:s.capacity})));
  if(detailErr){
    await admin.from('ministaut_koteng_scans').delete().eq('id',scan.id).eq('reading_status','observed');
    return json(500,{error:'Failed section write; scan rolled back'});
  }
  return json(200,{ok:true,scan_id:scan.id,status:'observed',available_seated:total});
});