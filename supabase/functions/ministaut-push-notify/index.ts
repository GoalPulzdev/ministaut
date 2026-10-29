import 'jsr:@supabase/functions-js/edge-runtime.d.ts';
import { createClient } from 'npm:@supabase/supabase-js@2.95.0';
import webpush from 'npm:web-push@3.6.7';
// Called by pg_cron every 10 minutes. For each match with alerts, looks at the newest
// public scan once and sends: "new tickets released" (seats went up) and
// "field X is running low" (a field crossed the chosen threshold; one-shot).
const admin=createClient(Deno.env.get('SUPABASE_URL')!,Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!,{auth:{persistSession:false}});
const SITE=Deno.env.get('MINISTAUT_SITE_URL')||'https://ministaut-web.vercel.app/';
const RELEASE_MIN=20;              // seats more than the previous handled scan
const RELEASE_COOLDOWN=2*3600000;  // at most one release alert per browser and match per 2 h
webpush.setVapidDetails('mailto:'+(Deno.env.get('VAPID_CONTACT')||'tom@goalpulz.com'),Deno.env.get('VAPID_PUBLIC_KEY')!,Deno.env.get('VAPID_PRIVATE_KEY')!);
const SOURCES={
  lerkendal:{matches:'ministaut_matches',scans:'ministaut_scans',sections:'ministaut_section_measurements',statuses:['accepted']},
  koteng_arena:{matches:'ministaut_koteng_matches',scans:'ministaut_koteng_scans',sections:'ministaut_koteng_section_measurements',statuses:['observed','accepted']},
} as const;
type Venue=keyof typeof SOURCES;
type Scan={id:string,observed_at:string,available_seated:number,locked_fields:string[]|null};
type Sub={id:string,endpoint:string,p256dh:string,auth:string,match_id:string,venue_id:Venue,kind:string,section_code:string,threshold:number|null,last_notified_at:string|null};
const json=(status:number,value:unknown)=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});
const fmt=(n:number)=>new Intl.NumberFormat('nb-NO').format(n);
const sameLocks=(a:Scan,b:Scan)=>JSON.stringify([...(a.locked_fields||[])].sort())===JSON.stringify([...(b.locked_fields||[])].sort());
const fieldName=(code:string)=>code==='VIP'?'VIP':code.startsWith('FELT-')?'Felt '+code.slice(5):'Felt '+code;
function safeEqual(a:string,b:string){
  if(!a||a.length!==b.length)return false;
  let d=0;for(let i=0;i<a.length;i++)d|=a.charCodeAt(i)^b.charCodeAt(i);
  return d===0;
}
let gone=new Set<string>();
async function send(sub:Sub,payload:Record<string,string>){
  if(gone.has(sub.endpoint))return false;
  try{
    await webpush.sendNotification({endpoint:sub.endpoint,keys:{p256dh:sub.p256dh,auth:sub.auth}},JSON.stringify(payload),{TTL:3600,urgency:'high'});
    return true;
  }catch(e){
    const status=(e as {statusCode?:number}).statusCode;
    // The browser unsubscribed or the subscription expired: forget it everywhere.
    if(status===404||status===410){gone.add(sub.endpoint);await admin.from('ministaut_push_subscriptions').delete().eq('endpoint',sub.endpoint);}
    return false;
  }
}
async function sections(venue:Venue,scanId:string){
  const {data}=await admin.from(SOURCES[venue].sections).select('section_code,free').eq('scan_id',scanId);
  return new Map((data||[]).map((r:{section_code:string,free:number})=>[r.section_code,r.free]));
}
Deno.serve(async req=>{
  if(req.method!=='POST')return json(405,{error:'POST required'});
  if(!safeEqual(req.headers.get('x-cron-secret')||'',Deno.env.get('PUSH_CRON_SECRET')||''))return json(401,{error:'Unauthorized'});
  gone=new Set();
  const {data:subs,error}=await admin.from('ministaut_push_subscriptions').select('*');
  if(error)return json(500,{error:'Could not read subscriptions'});
  const byMatch=new Map<string,Sub[]>();
  for(const s of (subs||[]) as Sub[]){if(!byMatch.has(s.match_id))byMatch.set(s.match_id,[]);byMatch.get(s.match_id)!.push(s);}
  const report:Record<string,unknown>[]=[];
  for(const [matchId,list] of byMatch){
    const venue=list[0].venue_id,src=SOURCES[venue];
    const {data:match}=await admin.from(src.matches).select('title,kickoff_at,event_key').eq('id',matchId).maybeSingle();
    const kickoff=Date.parse(match?.kickoff_at||'');
    // Played or removed match: alerts are no longer useful.
    if(!match||!(kickoff>Date.now())){
      await admin.from('ministaut_push_subscriptions').delete().eq('match_id',matchId);
      await admin.from('ministaut_push_state').delete().eq('match_id',matchId);
      report.push({matchId,removed:list.length});continue;
    }
    const {data:scans}=await admin.from(src.scans).select('id,observed_at,available_seated,locked_fields')
      .eq('match_id',matchId).in('reading_status',[...src.statuses]).order('observed_at',{ascending:false}).limit(2);
    const latest=(scans||[])[0] as Scan|undefined;
    if(!latest)continue;
    const {data:state}=await admin.from('ministaut_push_state').select('last_scan_id').eq('match_id',matchId).maybeSingle();
    if(state?.last_scan_id===latest.id)continue;
    // Compare with the scan handled last time; on the first run, with the scan before.
    let base:Scan|undefined;
    if(state){
      const {data}=await admin.from(src.scans).select('id,observed_at,available_seated,locked_fields').eq('id',state.last_scan_id).maybeSingle();
      base=(data as Scan)||undefined;
    }
    base=base||((scans||[])[1] as Scan|undefined);
    const url=SITE+'?kamp='+encodeURIComponent(match.event_key);
    let sent=0;
    if(base&&sameLocks(latest,base)){
      const up=latest.available_seated-base.available_seated;
      if(up>=RELEASE_MIN){
        for(const s of list.filter(s=>s.kind==='release'&&(!s.last_notified_at||Date.now()-Date.parse(s.last_notified_at)>RELEASE_COOLDOWN))){
          if(await send(s,{title:'Nye billetter: '+match.title,body:fmt(up)+' flere ledige sitteplasser siden forrige måling. Nå '+fmt(latest.available_seated)+' ledige.',url,tag:'release-'+matchId})){
            sent++;await admin.from('ministaut_push_subscriptions').update({last_notified_at:new Date().toISOString()}).eq('id',s.id);
          }
        }
      }
    }
    const fieldSubs=list.filter(s=>s.kind==='section');
    if(fieldSubs.length){
      const now=await sections(venue,latest.id),before=base?await sections(venue,base.id):new Map<string,number>();
      for(const s of fieldSubs){
        const free=now.get(s.section_code),prev=before.get(s.section_code);
        if(free===undefined||s.threshold===null||free>s.threshold)continue;
        if(prev!==undefined&&prev<=s.threshold)continue;
        if(await send(s,{title:fieldName(s.section_code)+': '+fmt(free)+' ledige igjen',body:match.title+'. Feltet har nå '+fmt(free)+' ledige sitteplasser.',url,tag:'field-'+matchId+'-'+s.section_code}))sent++;
        // One-shot: the alert has done its job (or the browser is gone).
        await admin.from('ministaut_push_subscriptions').delete().eq('id',s.id);
      }
    }
    await admin.from('ministaut_push_state').upsert({match_id:matchId,venue_id:venue,last_scan_id:latest.id,checked_at:new Date().toISOString()});
    report.push({matchId,scan:latest.id,sent});
  }
  return json(200,{ok:true,matches:report});
});
