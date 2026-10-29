import 'jsr:@supabase/functions-js/edge-runtime.d.ts';
import { createClient } from 'npm:@supabase/supabase-js@2.95.0';
// Public endpoint for the web page: subscribe, unsubscribe and list push alerts.
// The browser's push endpoint is the only identifier (no account, no e-mail).
const admin=createClient(Deno.env.get('SUPABASE_URL')!,Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!,{auth:{persistSession:false}});
const CORS={'Access-Control-Allow-Origin':'*','Access-Control-Allow-Methods':'POST, OPTIONS','Access-Control-Allow-Headers':'content-type, apikey, authorization, x-client-info'};
const json=(status:number,value:unknown)=>new Response(JSON.stringify(value),{status,headers:{...CORS,'Content-Type':'application/json','Cache-Control':'no-store'}});
// Only the browsers' own push services; anything else could be used to make us call arbitrary URLs.
const PUSH_HOSTS=/(^|\.)(fcm\.googleapis\.com|push\.services\.mozilla\.com|notify\.windows\.com|push\.apple\.com)$/;
const B64URL=/^[A-Za-z0-9_-]+={0,2}$/;
const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const MAX_PER_BROWSER=30;
type Sub={endpoint:string,keys:{p256dh:string,auth:string}};
function subscription(value:unknown):Sub|null{
  const s=value as Sub;
  if(!s||typeof s.endpoint!=='string'||s.endpoint.length>800||!s.keys)return null;
  let url:URL;
  try{url=new URL(s.endpoint);}catch{return null;}
  if(url.protocol!=='https:'||!PUSH_HOSTS.test(url.hostname))return null;
  const {p256dh,auth}=s.keys;
  if(typeof p256dh!=='string'||typeof auth!=='string'||!B64URL.test(p256dh)||!B64URL.test(auth)||p256dh.length>120||auth.length>40)return null;
  return {endpoint:s.endpoint,keys:{p256dh,auth}};
}
async function findMatch(id:string){
  for(const [table,venue] of [['ministaut_matches','lerkendal'],['ministaut_koteng_matches','koteng_arena']] as const){
    const {data}=await admin.from(table).select('id,kickoff_at,is_published').eq('id',id).maybeSingle();
    if(data)return {...data,venue_id:venue};
  }
  return null;
}
async function list(endpoint:string){
  const {data}=await admin.from('ministaut_push_subscriptions').select('match_id,kind,section_code,threshold').eq('endpoint',endpoint);
  return data||[];
}
Deno.serve(async req=>{
  if(req.method==='OPTIONS')return new Response(null,{status:204,headers:CORS});
  if(req.method!=='POST')return json(405,{error:'POST required'});
  const p=await req.json().catch(()=>null);
  const sub=subscription(p?.subscription);
  if(!sub)return json(422,{error:'Ugyldig varselregistrering'});
  if(p.action==='list')return json(200,{alerts:await list(sub.endpoint)});
  const matchId=String(p.match_id||''),kind=p.kind;
  if(!UUID.test(matchId)||(kind!=='release'&&kind!=='section'))return json(422,{error:'Ugyldig kamp eller varseltype'});
  const code=kind==='section'?String(p.section_code||''):'';
  if(kind==='section'&&!/^[A-Z0-9-]{1,12}$/.test(code))return json(422,{error:'Ugyldig felt'});
  if(p.action==='unsubscribe'){
    await admin.from('ministaut_push_subscriptions').delete().eq('endpoint',sub.endpoint).eq('match_id',matchId).eq('kind',kind).eq('section_code',code);
    return json(200,{alerts:await list(sub.endpoint)});
  }
  if(p.action!=='subscribe')return json(422,{error:'Ukjent handling'});
  const threshold=kind==='section'?Number(p.threshold):null;
  if(kind==='section'&&!(Number.isInteger(threshold)&&threshold!>=1&&threshold!<=500))return json(422,{error:'Ugyldig grense'});
  const match=await findMatch(matchId);
  if(!match||match.is_published!==true||!(Date.parse(match.kickoff_at)>Date.now()))return json(422,{error:'Kampen tar ikke imot varsler'});
  const {count}=await admin.from('ministaut_push_subscriptions').select('id',{count:'exact',head:true}).eq('endpoint',sub.endpoint);
  if((count||0)>=MAX_PER_BROWSER)return json(429,{error:'For mange varsler i denne nettleseren'});
  const {error}=await admin.from('ministaut_push_subscriptions').upsert({
    endpoint:sub.endpoint,p256dh:sub.keys.p256dh,auth:sub.keys.auth,match_id:matchId,venue_id:match.venue_id,
    kind,section_code:code,threshold,last_notified_at:null
  },{onConflict:'endpoint,match_id,kind,section_code'});
  if(error)return json(500,{error:'Kunne ikke lagre varselet'});
  return json(200,{alerts:await list(sub.endpoint)});
});
