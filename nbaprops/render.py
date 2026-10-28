"""PropHet sayfası: tüm günleri tek bir HTML'e (docs/index.html) basar. Telefon ve bilgisayarda çalışır."""
import glob
import json
import os
import urllib.parse

ROOT = os.path.join(os.path.dirname(__file__), "..")

LOGO = ('<svg viewBox="0 0 48 48" width="{w}" height="{w}" aria-hidden="true">'
        '<path d="M12 44 L15.5 36 H32.5 L36 44 Z" fill="#14213D"/>'
        '<circle cx="24" cy="21" r="15" fill="#E8792B"/>'
        '<g fill="none" stroke="#14213D" stroke-width="1.6"><path d="M9 21 H39"/><path d="M24 6 V36"/>'
        '<path d="M13.6 10.4 C19 15 19 27 13.6 31.6"/><path d="M34.4 10.4 C29 15 29 27 34.4 31.6"/></g>'
        '<path d="M40.5 4.5 l1.3 2.9 2.9 1.3 -2.9 1.3 -1.3 2.9 -1.3 -2.9 -2.9 -1.3 2.9 -1.3z" fill="#2348A8"/></svg>')

PAGE = r"""<!DOCTYPE html>
<html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PropHet</title>
<link rel="icon" href="__FAVICON__">
<link href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@600;800&family=Schibsted+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{
 --paper:#F3F5F7; --sheet:#FFFFFF; --ink:#14213D; --ink2:#4A5468; --mute:#7C8496; --rule:#E2E6EC;
 --court:#2348A8; --hl:#FFE45C; --win:#1E8E5A; --loss:#C8372D; --ball:#E8792B;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.45 "Schibsted Grotesk",system-ui,sans-serif;font-variant-numeric:tabular-nums}
a{color:inherit}
button,input{font:inherit;color:inherit}
:focus-visible{outline:2px solid var(--court);outline-offset:2px;border-radius:4px}
.wrap{max-width:1120px;margin:0 auto;padding:20px 18px 60px}

/* masthead */
.mast{display:flex;align-items:center;justify-content:space-between;gap:16px;padding-bottom:18px;border-bottom:2px solid var(--ink)}
.brand{display:flex;align-items:center;gap:10px;text-decoration:none}
.brand b{font:800 30px/1 "Big Shoulders Display",sans-serif;letter-spacing:.3px}
.nav{display:flex;gap:4px}
.nav a{font-weight:600;font-size:14px;text-decoration:none;padding:7px 12px;border-radius:8px;color:var(--ink2)}
.nav a[aria-current="page"]{background:var(--ink);color:#fff}

/* hero */
.hero{padding:26px 0 18px;display:grid;grid-template-columns:1fr auto;gap:18px 30px;align-items:end}
.hero h1{margin:0;font:800 clamp(44px,8vw,84px)/.9 "Big Shoulders Display",sans-serif;letter-spacing:-.5px}
.hero p{margin:10px 0 0;font-size:17px;color:var(--ink2);max-width:60ch}
.hero p strong{color:var(--ink)}
.stats{display:flex;gap:26px}
.stat b{display:block;font:800 34px/1 "Big Shoulders Display",sans-serif}
.stat span{font-size:13px;color:var(--mute)}
.pos{color:var(--win)}.neg{color:var(--loss)}.mute{color:var(--mute)}

/* date strip */
.dates{display:flex;gap:6px;overflow-x:auto;padding:4px 0 14px;scrollbar-width:none}
.dates::-webkit-scrollbar{display:none}
.dates a{flex:none;text-decoration:none;text-align:center;min-width:58px;padding:7px 8px 6px;border:1px solid var(--rule);border-radius:10px;background:var(--sheet)}
.dates a small{display:block;font-size:11px;color:var(--mute)}
.dates a span{font:800 20px/1 "Big Shoulders Display",sans-serif}
.dates a[aria-current="page"]{background:var(--court);border-color:var(--court);color:#fff}
.dates a[aria-current="page"] small{color:#C9D5F5}

.tools{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:4px 0 12px;font-size:14px;color:var(--ink2)}
.switch{display:inline-flex;align-items:center;gap:8px;cursor:pointer}
.switch input{width:18px;height:18px;accent-color:var(--court)}

/* game sheet */
.game{background:var(--sheet);border:1px solid var(--rule);border-radius:14px;margin-bottom:18px;overflow:hidden}
.ghead{display:grid;grid-template-columns:1fr auto;align-items:center;gap:6px 16px;padding:14px 18px;border-bottom:1px solid var(--rule)}
.teams{display:flex;align-items:center;gap:10px;font:800 26px/1 "Big Shoulders Display",sans-serif}
.teams img{width:28px;height:28px;object-fit:contain}
.teams .vs{font-weight:600;color:var(--mute);font-size:18px}
.teams .proj{font-weight:600;font-size:22px;color:var(--court)}
.gmeta{font-size:13px;color:var(--mute);grid-column:1/-1}
.gscore{text-align:right;font-size:13px;color:var(--ink2)}
.gscore b{font:800 22px/1 "Big Shoulders Display",sans-serif;color:var(--ink);margin-right:4px}
.ctx{padding:8px 18px;font-size:13px;color:var(--ink2);background:#F7F9FC;border-bottom:1px solid var(--rule)}
.ctx b{color:var(--ink)}

/* pick rows */
.cols,.pick{display:grid;grid-template-columns:minmax(170px,1.3fr) 138px minmax(160px,1.5fr) 50px 54px 70px 78px 78px 104px;gap:0 12px;align-items:center;padding:0 18px}
.cols{font-size:12px;color:var(--mute);padding-top:9px;padding-bottom:7px;border-bottom:1px solid var(--rule)}
.cols .r,.pick .r{text-align:right}
.pick{padding-top:11px;padding-bottom:11px;border-bottom:1px solid var(--rule)}
.pick:last-child{border-bottom:0}
.pick.bet{background:linear-gradient(90deg,#FFFBE0,#FFFFFF 70%)}
.who{display:flex;align-items:center;gap:10px;min-width:0}
.who img,.who .ph{width:38px;height:38px;border-radius:50%;object-fit:cover;background:#E9EDF3;flex:none}
.who .n{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.who .t{font-size:12px;color:var(--mute)}
.who .t .inj{color:var(--loss);font-weight:600}
.sel b{font:800 21px/1 "Big Shoulders Display",sans-serif}
.sel .m{font-size:13px;color:var(--ink2)}
.sel .src{font-size:11px;color:var(--mute)}
.why{grid-column:1/-1;font-size:12.5px;color:var(--ink2);padding:4px 0 0 48px}
.why span+span::before{content:"";display:inline-block;width:4px;height:4px;border-radius:50%;background:var(--rule);margin:0 8px 2px}

/* the meter */
.meter{position:relative}
.track{position:relative;height:10px;background:#EAEEF4;border-radius:5px}
.fill{position:absolute;left:0;top:0;bottom:0;background:var(--ink);border-radius:5px}
.edge{position:absolute;top:0;bottom:0;background:var(--win)}
.short{position:absolute;top:0;bottom:0;background:repeating-linear-gradient(135deg,#F1B7B1 0 3px,#F8DAD6 3px 6px)}
.be{position:absolute;top:-4px;bottom:-4px;width:2px;background:var(--ball);border-radius:1px}
.mlab{display:flex;justify-content:space-between;font-size:12px;color:var(--mute);margin-top:5px}
.mlab b{font-size:15px;color:var(--ink)}
.odds{font:800 20px/1 "Big Shoulders Display",sans-serif}
.val{font-weight:700}
.stake .hl{display:inline-block;background:var(--hl);padding:2px 7px;border-radius:4px;font-weight:700}
.stake .none{color:var(--mute)}
.res{font-size:13px}
.res b{font:800 20px/1 "Big Shoulders Display",sans-serif}
.res .min{display:block;font-size:12px;color:var(--mute)}
.badge{display:inline-block;font-size:12.5px;font-weight:700;padding:3px 9px;border-radius:6px;white-space:nowrap}
.badge.Tuttu{background:#DDF2E7;color:var(--win)}
.badge.Tutmadı{background:#F9E0DD;color:var(--loss)}
.badge.İade,.badge.Bekliyor{background:#EEF1F5;color:var(--ink2)}
.mine{display:flex;align-items:center;gap:6px}
.mine input[type=checkbox]{width:18px;height:18px;accent-color:var(--court);flex:none}
.mine input[type=number]{width:62px;padding:5px 6px;border:1px solid var(--rule);border-radius:6px;background:#fff;font-size:13px}
.empty{background:var(--sheet);border:1px dashed var(--rule);border-radius:14px;padding:40px 20px;text-align:center;color:var(--ink2)}

/* karne */
.kgrid{display:grid;grid-template-columns:1.2fr 1fr;gap:18px}
.panel{background:var(--sheet);border:1px solid var(--rule);border-radius:14px;padding:18px}
.panel h2{margin:0 0 4px;font:800 28px/1 "Big Shoulders Display",sans-serif}
.panel p{margin:6px 0 14px;color:var(--ink2);font-size:14px;max-width:62ch}
.calib{display:grid;gap:8px}
.crow{display:grid;grid-template-columns:70px 1fr 54px;gap:10px;align-items:center;font-size:13px}
.cbar{position:relative;height:18px;background:#EEF1F5;border-radius:4px}
.cbar .a{position:absolute;left:0;top:0;bottom:0;background:var(--court);border-radius:4px;opacity:.85}
.cbar .p{position:absolute;top:-3px;bottom:-3px;width:2px;background:var(--ball)}
.ktab{width:100%;border-collapse:collapse;font-size:14px}
.ktab th{font-weight:500;color:var(--mute);text-align:right;padding:6px 4px;border-bottom:1px solid var(--rule)}
.ktab th:first-child,.ktab td:first-child{text-align:left}
.ktab td{text-align:right;padding:7px 4px;border-bottom:1px solid var(--rule)}
.legend{display:flex;gap:16px;font-size:12px;color:var(--mute);margin-top:12px}
.legend i{display:inline-block;width:12px;height:8px;border-radius:2px;margin-right:5px;vertical-align:middle}
.foot{margin-top:30px;font-size:12.5px;color:var(--mute);max-width:80ch;line-height:1.55}

@media (max-width:900px){
 .hero{grid-template-columns:1fr}
 .cols{display:none}
 .pick{grid-template-columns:1fr auto;grid-template-areas:"who odds" "sel stake" "meter meter" "res status" "why why" "mine mine";gap:8px 12px;padding-top:14px;padding-bottom:14px}
 .who{grid-area:who}.sel{grid-area:sel}.meter{grid-area:meter}.odds{grid-area:odds}
 .val{display:none}.stake{grid-area:stake;text-align:right}
 .res{grid-area:res;text-align:left}.res .min{display:inline;margin-left:6px}.status{grid-area:status;text-align:right}
 .mine{grid-area:mine;justify-content:flex-start;font-size:13px;color:var(--mute)}
 .mine::after{content:"oynadım";order:-1;margin-right:2px}
 .why{padding-left:0}
 .kgrid{grid-template-columns:1fr}
 .stats{gap:18px}.stat b{font-size:28px}
}
@media (prefers-reduced-motion:no-preference){
 .fill{animation:grow .7s cubic-bezier(.2,.7,.2,1) both}
 @keyframes grow{from{width:0!important}}
}
</style></head><body>
<div class="wrap">
 <header class="mast">
  <a class="brand" href="#">__LOGO__<b>PropHet</b></a>
  <nav class="nav"><a href="#" id="nav-day">Tahminler</a><a href="#karne" id="nav-karne">Karne</a></nav>
 </header>
 <main id="app"></main>
 <p class="foot">Olasılık; model ile piyasanın (ABD siteleri varsa onların, yoksa iddaa oranının) karışımıdır, garanti değildir.
 Turuncu çizgi iddaa oranının başabaş noktasıdır, yeşil kısım avantajı gösterir. Stake çeyrek Kelly ile hesaplanır ve kasa, maç ve oyuncu limitleriyle sınırlanır.
 "Oynadım" işaretleri yalnızca bu tarayıcıda saklanır. Bahis 18 yaş altına yasaktır; kaybetmeyi göze alamayacağın parayla oynama.</p>
</div>
<script>
const DAYS=__DATA__, BT=__BACKTEST__;
const AY=["Ocak","Şubat","Mart","Nisan","Mayıs","Haziran","Temmuz","Ağustos","Eylül","Ekim","Kasım","Aralık"];
const AYK=["Oca","Şub","Mar","Nis","May","Haz","Tem","Ağu","Eyl","Eki","Kas","Ara"];
const GUN=["Pazar","Pazartesi","Salı","Çarşamba","Perşembe","Cuma","Cumartesi"], GK=["Paz","Pzt","Sal","Çar","Per","Cum","Cmt"];
const pct=x=>Math.round(x*100)+"%", esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const tr=iso=>new Date(new Date(iso).toLocaleString("en-US",{timeZone:"Europe/Istanbul"}));
const hhmm=d=>String(d.getHours()).padStart(2,"0")+":"+String(d.getMinutes()).padStart(2,"0");
const nightOf=day=>{const g=day.games[0];return g?tr(g.date_utc):new Date(day.date+"T12:00")};
const done=p=>p.result==="Tuttu"||p.result==="Tutmadı";

let PLAYED={},ONLY=false;
try{PLAYED=JSON.parse(localStorage.getItem("prophet_played")||"{}");ONLY=localStorage.getItem("prophet_only")==="1"}catch(e){}
const save=()=>{try{localStorage.setItem("prophet_played",JSON.stringify(PLAYED));localStorage.setItem("prophet_only",ONLY?"1":"0")}catch(e){}};
const key=(d,p)=>`${d}|${p.player_id}|${p.market}|${p.line}`;

function money(list,stakeOf){let risk=0,pl=0,n=0,w=0;
 list.forEach(d=>d.games.forEach(g=>g.picks.forEach(p=>{const s=stakeOf(d,p);if(!s||!done(p))return;
  risk+=s;n++;if(p.result==="Tuttu"){pl+=s*(p.odds-1);w++}else pl-=s})));return{risk,pl,n,w}}
const signed=x=>(x>=0?"+":"−")+Math.abs(Math.round(x));

function meter(p){
 const be=1/p.odds, pr=p.prob, lo=Math.min(be,pr), hi=Math.max(be,pr);
 return `<div class="meter" title="Olasılık ${pct(pr)}, başabaş ${pct(be)}">
  <div class="track"><div class="fill" style="width:${lo*100}%"></div>
  <div class="${pr>=be?"edge":"short"}" style="left:${lo*100}%;width:${(hi-lo)*100}%"></div>
  <div class="be" style="left:calc(${be*100}% - 1px)"></div></div>
  <div class="mlab"><span><b>${pct(pr)}</b> olasılık</span><span>başabaş ${pct(be)}</span></div></div>`}

function pickRow(day,p){
 const k=key(day.date,p), on=PLAYED[k]!==undefined, r=p.result||"Bekliyor";
 const why=[];
 if(p.prob_model!=null)why.push(`Model ${pct(p.prob_model)}, ${p.market_src==="ABD"?"ABD siteleri":"iddaa"} ${pct(p.prob_market)}`);
 if(p.us_line!=null)why.push(`ABD barem ${p.us_line} üst ${pct(p.us_p)} (${p.us_books} site)`);
 (p.notes||[]).forEach(n=>why.push(esc(n)));
 const act=p.actual==null?`<span class="mute">${p.expected.toFixed(1)}</span>`:`<b class="${p.actual>=p.line?"pos":"neg"}">${p.actual}</b>`;
 return `<div class="pick${p.stake_tl>0?" bet":""}">
  <div class="who">${p.headshot?`<img src="${esc(p.headshot)}" alt="" loading="lazy" onerror="this.replaceWith(Object.assign(document.createElement('span'),{className:'ph'}))">`:'<span class="ph"></span>'}
   <div style="min-width:0"><div class="n">${esc(p.player)}</div><div class="t">${esc(p.team)}${p.injury?` <span class="inj">${esc(p.injury)}</span>`:""}</div></div></div>
  <div class="sel"><b>${p.line}+</b> <span class="m">${esc(p.label)}</span><div class="src">${p.source==="IDDAA"?"iddaa":p.source==="MANUEL"?"elle girilen oran":"oran yok, adil oran"}</div></div>
  ${meter(p)}
  <div class="odds r">${p.odds.toFixed(2)}</div>
  <div class="val r ${p.value==null?"":p.value>=0?"pos":"neg"}">${p.value==null?"":(p.value>=0?"+":"−")+Math.abs(Math.round(p.value*100))+"%"}</div>
  <div class="stake r">${p.stake_tl>0?`<span class="hl">${p.stake_tl} ₺</span>`:'<span class="none">oynama</span>'}</div>
  <div class="res exp r">${act}<span class="min">${p.actual_min==null?`~${Math.round(p.proj_min)} dk`:`${p.actual_min} dk`}</span></div>
  <div class="status"><span class="badge ${r}">${r}</span></div>
  <div class="mine"><input type="checkbox" aria-label="Oynadım" data-k="${k}" ${on?"checked":""}><input type="number" min="1" inputmode="numeric" aria-label="Oynadığım tutar" data-s="${k}" placeholder="${p.stake_tl||10} ₺" value="${on?PLAYED[k]:""}"></div>
  ${why.length?`<div class="why">${why.map(w=>`<span>${w}</span>`).join("")}</div>`:""}
 </div>`}

function gameSheet(day,g){
 const picks=ONLY?g.picks.filter(p=>p.stake_tl>0):g.picks;
 if(ONLY&&!picks.length)return"";
 const d=tr(g.date_utc), dn=g.picks.filter(done), hit=dn.filter(p=>p.result==="Tuttu").length, exp=g.picks.reduce((a,p)=>a+p.prob,0);
 const tot=g.iddaa_total, ctx=Object.entries(g.context||{}).filter(([,n])=>n.length);
 const final=g.completed&&g.home.score!=null?`${g.away.abbr} ${g.away.score} – ${g.home.score} ${g.home.abbr}`:"";
 return `<section class="game">
  <div class="ghead"><div class="teams">${g.away.logo?`<img src="${esc(g.away.logo)}" alt="">`:""}${esc(g.away.abbr)}<span class="vs">@</span>${g.home.logo?`<img src="${esc(g.home.logo)}" alt="">`:""}${esc(g.home.abbr)}</div>
  <div class="gscore">${dn.length?`<b>${hit}/${dn.length}</b>tuttu, beklenen ${exp.toFixed(1)}`:`${g.picks.length} tahmin, beklenen ${exp.toFixed(1)} isabet`}</div>
  <div class="gmeta">${GK[d.getDay()]} ${hhmm(d)}${tot?`, iddaa toplam ${tot}`:""}${final?`, maç sonu ${final}`:""}</div></div>
  ${ctx.map(([t,n])=>`<div class="ctx"><b>${esc(t)}</b> ${n.map(esc).join(", ")}</div>`).join("")}
  <div class="cols"><span>Oyuncu</span><span>Seçim</span><span>Olasılık ve başabaş</span><span class="r">Oran</span><span class="r">Değer</span><span class="r">Stake</span><span class="r">Beklenen</span><span>Durum</span><span>Oynadım</span></div>
  ${picks.map(p=>pickRow(day,p)).join("")}
 </section>`}

function dayView(day){
 const n=nightOf(day), all=day.games.flatMap(g=>g.picks), bets=all.filter(p=>p.stake_tl>0), dn=all.filter(done);
 const stake=bets.reduce((a,p)=>a+p.stake_tl,0), hit=dn.filter(p=>p.result==="Tuttu").length;
 const m=money([day],(d,p)=>p.stake_tl), me=money(DAYS,(d,p)=>PLAYED[key(d.date,p)]);
 const pending=day.games.some(g=>(g.state||"pre")==="pre");
 const lead=pending
  ?`${day.games.length} maç, ${all.length} tahmin. <strong>${bets.length} bahis</strong> değer eşiğini geçti${bets.length?`, önerilen toplam stake <strong>${stake} ₺</strong>`:""}.`
  :`${dn.length} tahminden <strong>${hit} tanesi tuttu</strong>, model ${dn.reduce((a,p)=>a+p.prob,0).toFixed(1)} bekliyordu.${m.risk?` Stake'li bahisler ${signed(m.pl)} ₺.`:""}`;
 return `<section class="hero"><div><h1>${n.getDate()} ${AY[n.getMonth()]} ${GUN[n.getDay()]}</h1><p>${lead}</p></div>
  <div class="stats">
   <div class="stat"><b>${dn.length?pct(hit/dn.length):"–"}</b><span>bu gece isabet</span></div>
   <div class="stat"><b class="${!m.risk?"":m.pl>=0?"pos":"neg"}">${m.risk?signed(m.pl)+" ₺":"–"}</b><span>model stake K/Z</span></div>
   <div class="stat"><b class="${!me.risk?"":me.pl>=0?"pos":"neg"}">${me.risk?signed(me.pl)+" ₺":"–"}</b><span>benim K/Z, tüm günler</span></div>
  </div></section>
  ${dateStrip(day.date)}
  <div class="tools"><label class="switch"><input type="checkbox" id="only" ${ONLY?"checked":""}> Sadece stake önerilenleri göster</label>
   <span>Güncellendi ${hhmm(tr(day.generated))}</span></div>
  ${day.games.map(g=>gameSheet(day,g)).join("")||'<div class="empty">Bu gece maç yok.</div>'}`}

function dateStrip(cur){
 return `<nav class="dates" aria-label="Günler">${DAYS.slice().reverse().map(d=>{const n=nightOf(d);
  return `<a href="#d-${d.date}" ${d.date===cur?'aria-current="page"':""}><small>${GK[n.getDay()]}</small><span>${n.getDate()}</span><small>${AYK[n.getMonth()]}</small></a>`}).join("")}</nav>`}

function calib(items){
 const B=[[0,.3],[.3,.4],[.4,.5],[.5,.6],[.6,.7],[.7,.8],[.8,1.01]];
 return `<div class="calib">${B.map(([lo,hi])=>{const xs=items.filter(x=>x.p>=lo&&x.p<hi);if(!xs.length)return"";
  const pr=xs.reduce((a,x)=>a+x.p,0)/xs.length, ac=xs.reduce((a,x)=>a+x.h,0)/xs.length;
  return `<div class="crow"><span>%${Math.round(lo*100)}–${Math.round(Math.min(hi,1)*100)}</span>
   <div class="cbar" title="${xs.length} tahmin"><div class="a" style="width:${ac*100}%"></div><div class="p" style="left:${pr*100}%"></div></div>
   <b class="r">${pct(ac)}</b></div>`}).join("")}</div>
  <div class="legend"><span><i style="background:var(--court)"></i>gerçekleşen</span><span><i style="background:var(--ball);width:3px"></i>model tahmini</span></div>`}

function karne(){
 const live=[],mk={};
 DAYS.forEach(d=>d.games.forEach(g=>(g.all||[]).forEach(x=>{if(!done(x))return;const h=x.result==="Tuttu"?1:0;
  live.push({p:x.prob,h,v:x.value,o:x.odds});(mk[x.market]=mk[x.market]||[]).push({p:x.prob,h})})));
 const plus=live.filter(x=>x.v!=null&&x.v>=.05), roi=plus.length?plus.reduce((a,x)=>a+(x.h?x.o-1:-1),0)/plus.length:null;
 const m=money(DAYS,(d,p)=>p.stake_tl), me=money(DAYS,(d,p)=>PLAYED[key(d.date,p)]);
 const avg=xs=>xs.reduce((a,x)=>a+x,0)/xs.length;
 let h=`<section class="hero"><div><h1>Karne</h1><p>Model ne dedi, ne oldu. Model %60 dediğinde bahislerin yaklaşık %60'ı tutuyorsa olasılıklar güvenilirdir.</p></div>
  <div class="stats"><div class="stat"><b>${live.length?pct(avg(live.map(x=>x.h))):"–"}</b><span>${live.length} barem isabet</span></div>
  <div class="stat"><b class="${!m.risk?"":m.pl>=0?"pos":"neg"}">${m.risk?signed(m.pl)+" ₺":"–"}</b><span>model stake K/Z</span></div>
  <div class="stat"><b class="${!me.risk?"":me.pl>=0?"pos":"neg"}">${me.risk?signed(me.pl)+" ₺":"–"}</b><span>benim K/Z</span></div></div></section>
  <div class="kgrid"><div class="panel"><h2>Bu sezon, canlı</h2>`;
 h+=live.length?`<p>Sonuçlanan tüm iddaa baremleri, yalnızca seçilenler değil. Ortalama tahmin ${pct(avg(live.map(x=>x.p)))}, gerçekleşen ${pct(avg(live.map(x=>x.h)))}.
   Değeri +%5 üstünde olan ${plus.length} baremde 1 birimlik düz bahisle getiri ${roi==null?"–":(roi>=0?"+":"−")+Math.abs(Math.round(roi*100))+"%"}.</p>${calib(live)}
   <table class="ktab" style="margin-top:16px"><tr><th>Pazar</th><th>Adet</th><th>Tahmin</th><th>Gerçek</th></tr>${Object.entries(mk).map(([k,xs])=>`<tr><td>${k}</td><td>${xs.length}</td><td>${pct(avg(xs.map(x=>x.p)))}</td><td><b>${pct(avg(xs.map(x=>x.h)))}</b></td></tr>`).join("")}</table>`
  :`<p>Henüz sonuçlanan maç yok. Maçlar bitince sabah <b>python run.py --grade-only</b> çalışınca burası dolar.</p>`;
 h+=`</div><div class="panel"><h2>Geçen sezon testi</h2>`;
 h+=BT?`<p>${BT.season} sezonunun her maçı, yalnızca o güne kadarki veriyle tahmin edildi: ${BT.n.toLocaleString("tr-TR")} tahmin.
   Hata puanı ${BT.brier.toFixed(3)}; basit "son 10 maç" yöntemi ${BT.brier_naive.toFixed(3)}, yazı-tura 0.250 (düşük olan iyi).
   Barem olarak oyuncunun son 10 maç ortalaması kullanıldı, çünkü geçmiş iddaa oranları yok.</p>
   ${calib(BT.buckets.flatMap(b=>[{p:b.pred,h:b.act}]))}
   <table class="ktab" style="margin-top:16px"><tr><th>Pazar</th><th>Adet</th><th>Tahmin</th><th>Gerçek</th></tr>${Object.entries(BT.by_market).map(([k,v])=>`<tr><td>${k}</td><td>${v.n.toLocaleString("tr-TR")}</td><td>${pct(v.pred)}</td><td><b>${pct(v.act)}</b></td></tr>`).join("")}</table>`
  :`<p>Henüz çalıştırılmadı: <b>python run.py --backtest</b></p>`;
 return h+`</div></div>`}

function render(){
 const app=document.getElementById("app"), hsh=location.hash;
 const isK=hsh==="#karne";
 document.getElementById("nav-day").toggleAttribute("aria-current",!isK);document.getElementById("nav-karne").toggleAttribute("aria-current",isK);
 if(!isK)document.getElementById("nav-day").setAttribute("aria-current","page");else document.getElementById("nav-karne").setAttribute("aria-current","page");
 if(isK){app.innerHTML=karne();return}
 if(!DAYS.length){app.innerHTML='<div class="empty" style="margin-top:24px">Henüz tahmin yok. <b>python run.py</b> ile ilk günü oluştur.</div>';return}
 let d=hsh.startsWith("#d-")?hsh.slice(3):"";const day=DAYS.find(x=>x.date===d)||DAYS[DAYS.length-1];
 app.innerHTML=dayView(day);
}
document.addEventListener("change",e=>{const t=e.target;
 if(t.id==="only"){ONLY=t.checked;save();render();return}
 if(t.dataset.k){const inp=document.querySelector(`[data-s="${CSS.escape(t.dataset.k)}"]`);
  if(t.checked)PLAYED[t.dataset.k]=Math.max(1,+inp.value||parseFloat(inp.placeholder)||10);else delete PLAYED[t.dataset.k];save();render()}
 if(t.dataset.s&&PLAYED[t.dataset.s]!==undefined){PLAYED[t.dataset.s]=Math.max(1,+t.value||1);save();render()}});
addEventListener("hashchange",render);render();
</script></body></html>"""


def render(out_path=None, picks_dir=None):
    picks_dir = picks_dir or os.path.join(ROOT, "data", "picks")
    days = []
    for p in sorted(glob.glob(os.path.join(picks_dir, "*.json"))):
        with open(p, encoding="utf-8") as f:
            days.append(json.load(f))
    bt = None
    bt_path = os.path.join(ROOT, "data", "backtest.json")
    if os.path.exists(bt_path):
        with open(bt_path, encoding="utf-8") as f:
            bt = json.load(f)
    out_path = out_path or os.path.join(ROOT, "docs", "index.html")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fav = "data:image/svg+xml," + urllib.parse.quote(LOGO.format(w=48))
    html = (PAGE.replace("__LOGO__", LOGO.format(w=34)).replace("__FAVICON__", fav)
            .replace("__DATA__", json.dumps(days, ensure_ascii=False).replace("</", "<\\/"))
            .replace("__BACKTEST__", json.dumps(bt, ensure_ascii=False).replace("</", "<\\/")))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path
