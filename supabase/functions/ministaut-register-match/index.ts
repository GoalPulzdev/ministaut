import 'jsr:@supabase/functions-js/edge-runtime.d.ts';
import { createClient } from 'npm:@supabase/supabase-js@2.95.0';
// Scanner Control publishes a match on the web page when Live is switched on, so a new
// match (also on Koteng, whose ingest requires an existing row) needs no manual SQL.
// Same scanner token as the ingest functions; only title and kickoff can be updated.
const admin=createClient(Deno.env.get('SUPABASE_URL')!,Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!,{auth:{persistSession:false}});
const EVENT_KEY=/^[A-Za-z0-9_-]{8,100}$/;
const json=(status:number,value:unknown)=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json','Cache-Control':'no-store'}});
Deno.serve(async req=>{
  if(req.method!=='POST')return json(405,{error:'POST required'});
  const token=req.headers.get('x-ministaut-token')||'';
  if(!(/^[a-f0-9]{64}$/.test(token)||/^[A-Za-z0-9_-]{30,200}$/.test(token)))return json(401,{error:'Unauthorized'});
  const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(token)))).map(v=>v.toString(16).padStart(2,'0')).join('');
  const {data:identity,error:authError}=await admin.from('ministaut_scanner_tokens').select('token_name').eq('token_hash',digest).eq('enabled',true).maybeSingle();
  if(authError||!identity)return json(401,{error:'Unauthorized'});
  const p=await req.json().catch(()=>null);
  if(!p||typeof p!=='object')return json(422,{error:'Invalid JSON'});
  const eventKey=String(p.event_key||''),title=String(p.title||'').trim(),venue=p.venue_id;
  const kickoff=Date.parse(String(p.kickoff_at||''));
  if(!EVENT_KEY.test(eventKey))return json(422,{error:'Invalid event key'});
  if(title.length<3||title.length>120)return json(422,{error:'Title must be 3-120 characters'});
  if(!Number.isFinite(kickoff)||kickoff<Date.now()-6*3600000||kickoff>Date.now()+400*86400000)return json(422,{error:'Invalid kickoff'});
  const row={event_key:eventKey,title,kickoff_at:new Date(kickoff).toISOString(),is_published:true,updated_at:new Date().toISOString()};
  let table:string,values:Record<string,unknown>;
  if(venue==='lerkendal'){table='ministaut_matches';values={...row,total_capacity:21423};}
  else if(venue==='koteng_arena'){table='ministaut_koteng_matches';values={...row,venue_id:'koteng_arena',team_category:'women',total_capacity:601};}
  else return json(422,{error:'Unknown venue'});
  // One event belongs to one venue: refuse to publish it in the other table too.
  const other=venue==='lerkendal'?'ministaut_koteng_matches':'ministaut_matches';
  const {data:clash}=await admin.from(other).select('id').eq('event_key',eventKey).maybeSingle();
  if(clash)return json(409,{error:'Event already registered at the other venue'});
  const {data,error}=await admin.from(table).upsert(values,{onConflict:'event_key'}).select('id,event_key,title,kickoff_at,is_published').single();
  if(error||!data)return json(500,{error:'Could not register match'});
  return json(200,{ok:true,match:data,registered_by:identity.token_name});
});
