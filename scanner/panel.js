(() => {
  const ID = 'rbk-v16-live-panel';
  window.__rbkHUD ||= {command:'', mouse:{x:-1,y:-1,t:0,seq:0}};
  if (!window.__rbkHUD.tracking) {
    document.addEventListener('mousemove', e=>{ const m=window.__rbkHUD.mouse;
      m.x=e.clientX;m.y=e.clientY;m.t=Date.now();m.seq++; }, true);
    window.__rbkHUD.tracking = true;
  }
  if (document.getElementById(ID)) return true;
  const root=document.createElement('aside');root.id=ID;
  root.setAttribute('aria-label','RBK billettmonitor');
  root.innerHTML=`<style>
    #${ID}{--accent:#48efab;--mute:#96aa9f;position:fixed;right:12px;top:70px;width:356px;
      max-width:calc(100vw - 22px);max-height:calc(100vh - 80px);z-index:2147483646;
      background:linear-gradient(155deg,#102a20,#081810 70%);color:#effcf4;
      font:12px/1.35 'Segoe UI',system-ui,Arial,sans-serif;border:1px solid #2a5542;
      border-radius:17px;box-shadow:0 22px 65px #000b,0 0 0 1px #3bd99c16;overflow:auto;text-align:left;
      scrollbar-width:thin;scrollbar-color:#31624b transparent;direction:ltr}
    #${ID} *{box-sizing:border-box}
    #${ID} .head{position:sticky;top:0;z-index:1;padding:14px 15px 11px;background:#0c241b;
      display:flex;gap:8px;justify-content:space-between;align-items:center;border-bottom:1px solid #305b46;cursor:move}
    #${ID} .brand{color:var(--accent);font-size:11px;font-weight:850;letter-spacing:1.6px}
    #${ID} .sub{color:#aac8b8;font-size:10px;margin-top:3px}
    #${ID} .headbuttons{display:flex;gap:5px}
    #${ID} .headbuttons button{padding:5px 9px;background:#18392a;border:1px solid #35634c;font-size:14px;min-width:27px}
    #${ID} .content{padding:13px 13px 14px}
    #${ID} .event{font-weight:800;font-size:17px;letter-spacing:-.4px;margin-bottom:3px;overflow-wrap:anywhere}
    #${ID} .eventid{font-size:10px;color:var(--mute);margin-bottom:10px}
    #${ID} .state{display:flex;align-items:center;gap:7px;background:#18372b;border:1px solid #2b624a;
      color:#c1f5d8;border-radius:9px;padding:8px 9px;margin-bottom:10px;line-height:1.35}
    #${ID} .dot{width:7px;height:7px;flex-shrink:0;background:var(--accent);border-radius:50%;box-shadow:0 0 12px #40f8aa}
    #${ID} .stats{display:grid;grid-template-columns:1fr 1fr;gap:7px}
    #${ID} .stat{background:#132e24;border:1px solid #285640;padding:11px;border-radius:11px;min-width:0}
    #${ID} .stat.main{background:linear-gradient(135deg,#174932,#143027);border-color:#438a65}
    #${ID} .num{font-weight:850;font-size:25px;letter-spacing:-1px;color:#f7fff9;font-variant-numeric:tabular-nums}
    #${ID} .main .num{color:var(--accent);font-size:29px}
    #${ID} .caption{font-size:10px;color:#b6cfc1;margin-top:2px}
    #${ID} .progress{height:6px;background:#1f4a38;border-radius:8px;overflow:hidden;margin:10px 0 4px}
    #${ID} .progress>div{height:100%;width:0%;background:linear-gradient(90deg,#23ab73,#65ffc0);border-radius:8px;transition:width .25s}
    #${ID} .line{display:flex;justify-content:space-between;align-items:center;color:var(--mute);font-size:10px;gap:8px}
    #${ID} .delta{display:flex;gap:10px;align-items:center;justify-content:space-between;
      background:#10291f;border:1px solid #285943;border-radius:11px;padding:10px;margin-top:9px}
    #${ID} .delta b{font-size:23px;color:var(--accent);font-variant-numeric:tabular-nums}
    #${ID} .chart{width:128px;height:49px;min-width:128px;overflow:visible}
    #${ID} h3{margin:14px 0 6px;font-size:10px;color:#8ee8ba;letter-spacing:1.1px;text-transform:uppercase;font-weight:850}
    #${ID} button{font:650 11px 'Segoe UI',system-ui,sans-serif;cursor:pointer;appearance:none;
      border:1px solid #346c50;background:#1b4933;color:#effcf4;border-radius:8px;padding:9px 10px}
    #${ID} button:hover{background:#256848;border-color:#65b689}
    #${ID} button:focus-visible,#${ID} input:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
    #${ID} button:disabled{opacity:.48;cursor:wait}
    #${ID} .primary{width:100%;padding:13px 10px;background:#38e7a0;color:#092218;border:0;
      font-weight:900;font-size:14px;letter-spacing:.1px;box-shadow:0 6px 23px #23df9633}
    #${ID} .primary:hover{background:#7affc7;color:#071d13}
    #${ID} .actions{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:7px}
    #${ID} .actions button{min-height:35px}
    #${ID} .missing{display:flex;flex-wrap:wrap;gap:5px;max-height:95px;overflow:auto}
    #${ID} .missing button{background:#1d3428;padding:5px 8px;border-color:#476050}
    #${ID} .box{padding:9px;border:1px solid #315543;border-radius:10px;background:#0d231a;margin-top:8px}
    #${ID} label{display:block;color:#a8c2b3;font-size:10px;margin:0 0 4px}
    #${ID} input{background:#071a11;border:1px solid #39654e;border-radius:7px;outline:none;
      padding:9px;color:white;width:100%;font:12px 'Segoe UI',system-ui,sans-serif}
    #${ID} .inline{display:flex;gap:6px}
    #${ID} .inline input{flex:1;min-width:0}
    #${ID} .tiny{color:#90ab9a;font-size:10px;margin-top:7px;overflow-wrap:anywhere}
    #${ID}.closed{width:245px}#${ID}.closed .content{display:none}
    #${ID}.busy .restart{opacity:.5;pointer-events:none}
    #${ID} .confirmbox{margin:10px 0;border:1px solid #60e6a5;background:#133526;border-radius:12px;padding:13px;box-shadow:0 4px 23px #05180a66}
    #${ID} .confirmbox strong{display:block;color:#d7ffe9;font-size:13px;margin-bottom:6px}
    #${ID} .confirmbox p{font-size:11px;color:#d0ebdc;margin:0 0 11px;white-space:pre-wrap;overflow-wrap:anywhere}
    #${ID} .confirmrow{display:grid;grid-template-columns:1fr 1fr;gap:7px}
    #${ID} .confirmrow .approve{background:#33db94;color:#052117;font-weight:850}
    #${ID} .forecast-box{margin-top:9px;padding:11px 12px;border:1px solid #416c51;background:#0f2a20;border-radius:11px}
    #${ID} .forecast-number{font-size:24px;font-weight:850;color:#e7fff2;font-variant-numeric:tabular-nums}
    #${ID} .largechart{width:100%;height:120px;display:block;overflow:visible;margin-top:7px;background:#10271d;border-radius:8px}
    #${ID} .auto-box{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:10px 0;padding:10px 11px;background:#113124;border:1px solid #375f49;border-radius:11px}
    #${ID} .auto-box button{min-width:71px;font-weight:850}
    #${ID} .notice{font-size:11px;margin:7px 0;color:#b9edd0;min-height:16px;overflow-wrap:anywhere}
    #${ID} .notice.error{color:#ffacae}
    #${ID} .hidden{display:none!important}
    @media(max-width:640px){#${ID}{top:8px;right:8px;max-height:85vh;width:310px}}
  </style>
  <div class="head" id="rbk-draghead"><div><div class="brand">RBK • BILLETTMONITOR</div><div class="sub">V20 · automatisk overvåkning</div></div>
    <div class="headbuttons"><button type="button" data-action="dock" title="Flytt til motsatt side">⇆</button>
    <button type="button" data-action="fold" title="Minimer/utvid">−</button></div></div>
  <div class="content"><div class="event" id="rbk-title">Rosenborg · Billettstatus</div>
    <div class="eventid" id="rbk-match-id">Venter på kampdata</div>
    <div class="state" role="status"><span class="dot"></span><span id="rbk-mode">Klargjør første skanning …</span></div>
    <div class="stats"><div class="stat main"><div class="num" id="rbk-free">0</div><div class="caption" id="rbk-free-label">Ledige i avleste sittefelt</div></div>
    <div class="stat"><div class="num" id="rbk-estimated">–</div><div class="caption">Estimert ikke kjøpbare*</div></div>
    <div class="stat"><div class="num" id="rbk-found">0/60</div><div class="caption">Sittefelt avklart</div></div>
    <div class="stat"><div class="num" id="rbk-locked-count">0</div><div class="caption">Bekreftet låste bortefelt</div></div></div>
    <div class="progress"><div id="rbk-track"></div></div>
    <div class="line"><span id="rbk-missing-count">Sjekker felt …</span><span id="rbk-last-time">–</span></div>
    <div class="delta"><div><div class="caption">ENDRING SIDEN SIST</div><b id="rbk-delta">–</b><div class="tiny" id="rbk-delta-label">Vises ved komplett måling</div></div>
       <svg class="chart" id="rbk-spark" viewBox="0 0 128 49" aria-label="Historisk estimert ikke tilgjengelige"></svg></div>
    <div class="forecast-box"><div class="caption">LEDIGE PLASSER VED KAMPSTART · PROGNOSE</div>
       <div id="rbk-forecast-num" class="forecast-number">Venter på historikk</div>
       <div id="rbk-forecast-note" class="tiny">Minst 4 målinger over 6 timer kreves. Langt fram i tid vises ingen prognose.</div>
       <div class="caption" style="margin-top:9px">HISTORIKK · DOKUMENTERTE LEDIGE</div>
       <svg id="rbk-history-chart" class="largechart" viewBox="0 0 316 120" role="img" aria-label="Ledige sitteplasser over tid"></svg>
       <div class="tiny" style="display:flex;justify-content:space-between"><span>Grønn = målt</span><span>Oransje = estimert</span></div>
       <button data-action="open_chart" style="width:100%;margin-top:8px">↗ Åpne detaljert historikkgraf</button>
    </div>
    <div class="auto-box"><div><div style="font-weight:850;color:#c6ffdd">Automatisk hver 3. time</div>
       <div id="rbk-auto-next" class="tiny" style="margin:2px 0 0">Planlegger neste måling …</div></div>
       <button data-action="auto_toggle" id="rbk-auto-toggle">På</button></div>
    <div class="tiny">Edge, Python og PC må forbli åpne/våkne. Automatiske sjekker oppdaterer den dedikerte billettfanen.</div>
    <h3>Skanning</h3>
    <button class="primary restart" data-action="new_scan">↻  Ny sjekk av samme kamp</button>
    <div class="confirmbox hidden" id="rbk-confirm" role="group" aria-label="Bekreft handling">
      <strong id="rbk-confirm-title">Bekreft handling</strong><p id="rbk-confirm-desc"></p>
      <div class="confirmrow"><button class="approve" data-action="approve">Ja, fortsett</button>
      <button data-action="cancel">Avbryt</button></div>
    </div>
    <div class="notice" id="rbk-action-notice" aria-live="polite"></div>
    <div class="actions"><button data-action="save_final">Lagre + publiser</button><button data-action="retry">Prøv manglende</button>
      <button data-action="recalibrate">Oppdater kartmål</button><button data-action="stop">Avslutt sesjon</button>
      <button data-action="open_output">Åpne resultatmappe</button><button data-action="open_share">Vis statusbilde</button></div>
    <h3>Felt som mangler <span id="rbk-missing-total"></span></h3><div class="missing" id="rbk-missing">Venter …</div>
    <details class="box"><summary style="cursor:pointer;font-weight:700">Kampoppsett og bortefelt</summary>
      <label for="rbk-locked-input" style="margin-top:9px">Låste felt, opptil to (f.eks. RB,TB)</label>
      <div class="inline"><input id="rbk-locked-input" placeholder="Ingen låste felt" spellcheck="false" autocomplete="off"/>
      <button data-action="config_locked">Lagre</button></div>
      <div class="tiny">Bare felt du har bekreftet låst. Endring starter ny sjekk og ny sammenligningsserie.</div>
      <label for="rbk-saved-events" style="margin-top:11px">Mine kamper · uten omstart</label>
      <div class="inline"><select id="rbk-saved-events" style="min-width:0;flex:1;background:#112a20;color:#fff;border:1px solid #507a63;border-radius:6px;padding:8px"><option value="">Velg lagret kamp</option></select>
      <button data-action="select_registered">Åpne</button></div>
      <label for="rbk-kickoff" style="margin-top:11px">Avspark for valgt kamp (norsk tid)</label>
      <div class="inline"><input type="datetime-local" id="rbk-kickoff" style="min-width:0;flex:1"/><button data-action="save_kickoff">Lagre</button></div>
      <div class="tiny">Kampen telles til avspark og arkiveres automatisk. Koteng krever eget kontrollert kart.</div>
      <label for="rbk-switch-url" style="margin-top:11px">Legg til en ny kamp</label>
      <div class="inline"><input id="rbk-switch-url" placeholder="https://billett.rbk.no/checkout/…" spellcheck="false" autocomplete="off"/>
      <button data-action="register">Legg til</button></div>
      <div class="inline" style="margin-top:6px"><label for="rbk-new-venue">Arena</label><select id="rbk-new-venue" style="flex:1;background:#112a20;color:#fff;border:1px solid #507a63;border-radius:6px;padding:8px"><option value="lerkendal">Lerkendal</option><option value="koteng_arena">Koteng Arena</option></select></div></details>
    <div class="tiny" id="rbk-last">Ingen felt registrert ennå</div>
    <div class="tiny">* 21 423 minus dokumentert ledige. Ikke offisielle solgte billetter. Ståplassledighet ukjent.</div>
    <div class="tiny">Målehistorikken beholdes mellom sjekker. Panelet foretar aldri billettkjøp.</div>
  </div>`;
  document.documentElement.appendChild(root);
  // No native confirm()/alert()/prompt(): Playwright auto-dismisses dialogs unless
  // a handler is registered. That silently prevented both V19 control buttons.
  let pending=null;
  const box=root.querySelector('#rbk-confirm');
  const note=root.querySelector('#rbk-action-notice');
  function notice(message,error=false){note.textContent=message;note.classList.toggle('error',error);}
  function closeConfirm(){pending=null;box.classList.add('hidden');}
  function ask(command,title,description){
    pending=command;
    root.querySelector('#rbk-confirm-title').textContent=title;
    root.querySelector('#rbk-confirm-desc').textContent=description;
    box.classList.remove('hidden');
    note.textContent='';
    box.scrollIntoView({block:'nearest',behavior:'instant'});
  }
  function cmd(value){
    if(window.__rbkHUD.command){notice('Forrige kommando er ikke hentet ennå. Prøv igjen om et øyeblikk.',true);return;}
    window.__rbkHUD.command=value;
    notice('Kommando sendt til skanneren. Venter på behandling …');
  }
  root.addEventListener('click',event=>{
    const btn=event.target.closest('button[data-action]');if(!btn)return;
    event.preventDefault();event.stopPropagation();
    const action=btn.dataset.action;
    if(action==='fold'){const closed=root.classList.toggle('closed');btn.textContent=closed?'+':'−';return;}
    if(action==='dock'){const left=root.style.left==='12px';root.style.left=left?'':'12px';root.style.right=left?'12px':'';return;}
    if(action==='cancel'){closeConfirm();notice('Handlingen ble avbrutt.');return;}
    if(action==='approve'){
      if(!pending){notice('Ingen handling å bekrefte.',true);return;}
      const selected=pending;closeConfirm();cmd(selected);return;
    }
    if(action==='auto_toggle' || action==='open_chart'){cmd(action);return;}
    if(action==='new_scan'){
      if(btn.disabled){notice('En måling pågår allerede.',true);return;}
      ask('new_scan','Start ny sjekk?',
          'Den gjeldende målingen lagres først. Billettkartet lastes på nytt, og alle felt telles fra null. Ikke fortsett hvis du har en aktiv handlekurv.');
      return;
    }
    if(action==='config_locked'){
      const value=root.querySelector('#rbk-locked-input').value.trim().toUpperCase();
      if(value && !/^[A-ZÆØÅ]+(?:\s*,\s*[A-ZÆØÅ]+)?$/.test(value)){
        notice('Oppgi ett eller to feltnavn, for eksempel RB,TB.',true);return;
      }
      ask('locked:'+value,'Bekreft låste bortefelt',
          'Felt: '+(value||'Ingen')+'.\nBare bekreftet låste felt kan registreres. Det starter deretter en ny skanning.');
      return;
    }
    if(action==='save_kickoff'){
      const key=root.querySelector('#rbk-saved-events').value;
      const time=root.querySelector('#rbk-kickoff').value;
      if(!key||!time){notice('Velg kamp og angi avspark.',true);return;}
      ask('kickoff:'+key+'|'+time,'Lagre kampstart?','Kampen overvåkes bare fram til dette tidspunktet (norsk tid).');
      return;
    }
        if(action==='select_registered'){
      const key=root.querySelector('#rbk-saved-events').value;
      if(!key){notice('Velg en kamp fra listen først.',true);return;}
      ask('select_registered:'+key,'Åpne lagret kamp?','Den aktive målingen lagres før du bytter kamp.');
      return;
    }
        if(action==='register'){
      const value=root.querySelector('#rbk-switch-url').value.trim();
      const venue=root.querySelector('#rbk-new-venue').value;
      let valid=false;
      try{const u=new URL(value);valid=u.protocol==='https:'&&u.hostname==='billett.rbk.no'&&/^\/checkout\/[A-Za-z0-9_-]{8,100}\/?$/.test(u.pathname);}catch(e){}
      if(!valid){notice('Bruk en gyldig RBK-billettlenke.',true);return;}
      ask('register:'+value+'|'+venue,'Legg til kamp?', 'Kampen lagres i listen uten å avbryte aktiv skanning. Angi avspark etterpå.');
      return;
    }
    if(action==='switch'){
      const value=root.querySelector('#rbk-switch-url').value.trim();
      let valid=false;
      try{const u=new URL(value);valid=u.protocol==='https:' && u.hostname==='billett.rbk.no' && /^\/checkout\/[^/]+\/?$/.test(u.pathname);}catch(e){}
      if(!valid){notice('Ugyldig adresse. Lim inn https://billett.rbk.no/checkout/<kamp-id>.',true);return;}
      ask('switch:'+value,'Bytt til en annen kamp?',
          'Nåværende måling lagres først. Deretter lastes denne kampens billettkart:\n'+value+'\nIkke fortsett med aktiv handlekurv.');
      return;
    }
    cmd(action);
  });
  function renderNext(){
    const target=Number(root.dataset.nextScanAt||0),enabled=root.dataset.autoEnabled==='true';
    const node=root.querySelector('#rbk-auto-next');if(!node)return;
    if(!enabled){node.textContent='Avslått · bare manuelle sjekker';return;}
    if(!target){node.textContent='Planlegger neste sjekk …';return;}
    const secs=Math.max(0,Math.floor((target-Date.now())/1000));
    node.textContent=secs===0?'Neste sjekk starter snart':`Neste om ${Math.floor(secs/3600)} t ${Math.floor((secs%3600)/60)} min`;
  }
  setInterval(renderNext,30000);renderNext();
  const head=root.querySelector('#rbk-draghead');let origin=null;
  head.addEventListener('pointerdown',e=>{if(e.target.closest('button'))return;
    origin={x:e.clientX,y:e.clientY,left:root.getBoundingClientRect().left,top:root.getBoundingClientRect().top};
    head.setPointerCapture(e.pointerId);
  });
  head.addEventListener('pointermove',e=>{if(!origin)return;
    const x=Math.min(window.innerWidth-70,Math.max(4,origin.left+e.clientX-origin.x));
    const y=Math.min(window.innerHeight-55,Math.max(4,origin.top+e.clientY-origin.y));
    root.style.left=x+'px';root.style.top=y+'px';root.style.right='auto';
  });
  head.addEventListener('pointerup',()=>{origin=null});
  return true;
})()