"""LifePilot UI — served by the running backend, so every control is live.

Design system: Singh Studio (S·/·S)
  ink #0c0b09 · bone #ece7dd · red #e23b22 · mute #9a938a · hairline
  Switzer-style display, IBM Plex Serif italic "voice", Fragment-mono labels
  The slash is the brand device.

Every interaction calls the real FastAPI endpoints — nothing here is mocked.
Fonts are local system stacks because the sandbox cannot reach a CDN.
"""

from __future__ import annotations

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LifePilot — propose, never presume</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  /* Singh Studio tokens, verbatim */
  --ink:#0c0b09; --ink-2:#14120f; --ink-3:#1d1a16;
  --bone:#ece7dd; --bone-2:#e2dcd0;
  --mute:#9a938a; --mute-dark:#6d675f;
  --red:#e23b22; --red-hot:#ff4b2e;
  --hairline:rgba(236,231,221,.14);
  --copy:#d8d2c6;
  --font-display:"Switzer","Helvetica Neue",Helvetica,Arial,sans-serif;
  --font-serif:"PlexSerif",Georgia,"Times New Roman",serif;
  --font-mono:"Fragment","SF Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
  --ease-out:cubic-bezier(.19,1,.22,1);
  --ease-swift:cubic-bezier(.65,0,.15,1);
  --pad:clamp(1.25rem,4vw,3.5rem);
  color-scheme:dark;
}
html{scroll-behavior:smooth}
body{
  background:var(--ink); color:var(--bone);
  font-family:var(--font-display); font-weight:400; line-height:1.6;
  -webkit-font-smoothing:antialiased; min-height:100vh;
}
::selection{background:var(--red);color:var(--bone)}
em{font-family:var(--font-serif);font-style:italic;font-weight:400}
button{font:inherit;color:inherit;background:none;border:0;cursor:pointer}
input,textarea{font:inherit;color:inherit}
a{color:inherit;text-decoration:none}
:focus-visible{outline:2px solid var(--red);outline-offset:3px}

.wrap{max-width:1180px;margin:0 auto;padding:0 var(--pad) 5rem}

/* ---------- chrome ---------- */
.progress{position:fixed;top:0;left:0;right:0;height:2px;z-index:50}
.progress span{display:block;height:100%;background:var(--red);transform:scaleX(0);
  transform-origin:left;transition:transform .15s linear}

/* ---------- nav ---------- */
nav{display:flex;justify-content:space-between;align-items:center;
  padding:1.6rem 0;border-bottom:1px solid var(--hairline);gap:1.5rem;flex-wrap:wrap}
.brand{display:flex;align-items:baseline;gap:.55rem;font-weight:620;
  font-size:1.45rem;letter-spacing:-.02em}
.brand .slash{color:var(--red);font-family:var(--font-serif);font-style:italic}
.brand small{font-family:var(--font-mono);font-size:.62rem;letter-spacing:.16em;
  text-transform:uppercase;color:var(--mute);margin-left:.5rem}
nav .right{display:flex;align-items:center;gap:1.2rem;flex-wrap:wrap}
.pill-link{font-family:var(--font-mono);font-size:.7rem;letter-spacing:.13em;
  text-transform:uppercase;color:var(--mute);transition:color .25s}
.pill-link:hover{color:var(--bone)}
.live{font-family:var(--font-mono);font-size:.66rem;letter-spacing:.13em;
  text-transform:uppercase;color:var(--bone);display:flex;align-items:center;gap:.5rem}
.live i{width:6px;height:6px;border-radius:50%;background:var(--red);
  box-shadow:0 0 0 0 rgba(226,59,34,.7);animation:pulse 2s infinite}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(226,59,34,.6)}70%{box-shadow:0 0 0 9px rgba(226,59,34,0)}100%{box-shadow:0 0 0 0 rgba(226,59,34,0)}}

/* ---------- hero ---------- */
.hero{padding:clamp(3rem,8vh,5.5rem) 0 clamp(2rem,5vh,3.5rem)}
.eyebrow{font-family:var(--font-mono);font-size:.72rem;letter-spacing:.14em;
  text-transform:uppercase;color:var(--mute);display:flex;gap:.5rem}
.eyebrow .slash{color:var(--red)}
h1{font-size:clamp(2.4rem,6.5vw,4.6rem);font-weight:620;letter-spacing:-.025em;
  line-height:.94;margin:1.1rem 0 0;max-width:15ch}
h1 .red{color:var(--red)}
.hero p{color:var(--copy);font-size:clamp(.95rem,1.4vw,1.1rem);max-width:52ch;margin-top:1.4rem}
.hero p em{color:var(--bone)}

/* ---------- layout ---------- */
.grid{display:grid;grid-template-columns:1.05fr 1fr;gap:1.1rem;align-items:start}
@media(max-width:940px){.grid{grid-template-columns:1fr}}

/* ---------- card ---------- */
.card{background:var(--ink-2);border:1px solid var(--hairline);border-radius:2px;
  padding:1.4rem 1.4rem 1.5rem}
.card + .card{margin-top:1.1rem}
.chead{display:flex;justify-content:space-between;align-items:baseline;
  gap:1rem;margin-bottom:1.15rem;flex-wrap:wrap}
.chead h2{font-size:1.02rem;font-weight:620;letter-spacing:-.01em}
.note{font-family:var(--font-mono);font-size:.66rem;letter-spacing:.1em;
  text-transform:uppercase;color:var(--mute-dark)}

/* ---------- inputs ---------- */
textarea,input[type=text]{
  width:100%;background:var(--ink-3);border:1px solid var(--hairline);
  border-radius:2px;padding:.85rem 1rem;font-size:.95rem;line-height:1.5;
  color:var(--bone);resize:vertical;transition:border-color .25s}
textarea{min-height:72px}
textarea::placeholder,input::placeholder{color:var(--mute-dark)}
textarea:focus,input[type=text]:focus{outline:none;border-color:var(--red)}

.btn{display:inline-flex;align-items:center;gap:.55rem;font-family:var(--font-mono);
  font-size:.72rem;text-transform:uppercase;letter-spacing:.12em;
  padding:.8rem 1.35rem;border-radius:999px;
  transition:background .35s var(--ease-swift),color .35s var(--ease-swift),
             border-color .35s var(--ease-swift),transform .35s var(--ease-out);
  white-space:nowrap}
.btn-solid{background:var(--red);color:var(--bone)}
.btn-solid:hover{background:var(--red-hot)}
.btn-ghost{border:1px solid var(--hairline);color:var(--bone)}
.btn-ghost:hover{border-color:var(--bone)}
.btn:disabled{opacity:.4;cursor:not-allowed;transform:none}
.btn-arrow{transition:transform .35s var(--ease-out)}
.btn:hover .btn-arrow{transform:translateX(4px)}
.row{display:flex;gap:.6rem;flex-wrap:wrap;margin-top:.9rem}

.chips{display:flex;gap:.4rem;flex-wrap:wrap;margin-top:.95rem}
.chip{font-family:var(--font-mono);font-size:.66rem;letter-spacing:.05em;
  padding:.4rem .7rem;border:1px solid var(--hairline);border-radius:999px;
  color:var(--mute);transition:.2s}
.chip:hover{border-color:var(--red);color:var(--bone)}
.chip.bad:hover{border-color:var(--mute);color:var(--mute)}

/* ---------- result ---------- */
.result{margin-top:1rem;border-top:1px solid var(--hairline)}
.field{display:grid;grid-template-columns:88px 1fr;gap:1rem;padding:.85rem 0;
  border-bottom:1px solid var(--hairline)}
.field:last-child{border-bottom:none;padding-bottom:0}
.field .k{font-family:var(--font-mono);font-size:.66rem;letter-spacing:.11em;
  text-transform:uppercase;color:var(--mute-dark);padding-top:.15rem}
.field .v{font-size:.95rem;font-weight:620;letter-spacing:-.01em}
.field .why{font-family:var(--font-mono);font-size:.7rem;color:var(--mute);
  margin-top:.3rem;line-height:1.5;word-break:break-word}
.field select,.field input[type=date],.field input[type=number]{
  width:100%;background:var(--ink-3);border:1px solid var(--hairline);
  border-radius:2px;padding:.5rem .7rem;font-size:.9rem;font-weight:620;
  color:var(--bone);font-family:var(--font-display)}
.field select:focus,.field input:focus{outline:none;border-color:var(--red)}
.tag{display:inline-block;font-family:var(--font-mono);font-size:.66rem;
  letter-spacing:.09em;text-transform:uppercase;padding:.25rem .6rem;
  border:1px solid var(--hairline);border-radius:999px;color:var(--bone)}
.tag.p1{border-color:var(--red);color:var(--red);background:rgba(226,59,34,.1)}
.tag.p2{border-color:rgba(226,59,34,.5);color:var(--bone);background:rgba(226,59,34,.05)}

/* ---------- chat ---------- */
.chat{display:flex;flex-direction:column;gap:.7rem;max-height:330px;overflow-y:auto;
  padding-right:.35rem;margin-bottom:.9rem;scrollbar-width:thin}
.chat::-webkit-scrollbar{width:5px}
.chat::-webkit-scrollbar-thumb{background:var(--ink-3)}
.msg{padding:.72rem .95rem;border-radius:2px;font-size:.88rem;line-height:1.55;
  max-width:94%;white-space:pre-wrap;word-break:break-word;border:1px solid var(--hairline)}
.msg.user{align-self:flex-end;background:var(--ink-3);border-color:rgba(236,231,221,.22)}
.msg.bot{align-self:flex-start;background:transparent}
.msg .who{display:block;font-family:var(--font-mono);font-size:.6rem;letter-spacing:.14em;
  text-transform:uppercase;color:var(--red);margin-bottom:.3rem}
.msg.sys{align-self:stretch;border-style:dashed;color:var(--mute);
  font-family:var(--font-mono);font-size:.68rem;letter-spacing:.05em;text-align:center}
.chatinput{display:flex;gap:.55rem}
.chatinput input{flex:1;min-width:0}

/* ---------- task list ---------- */
.pending{border:1px solid var(--red);background:rgba(226,59,34,.06);
  padding:.9rem 1rem;border-radius:2px;margin-top:.9rem;display:none}
.pending.on{display:block;animation:rise .3s var(--ease-out)}
@keyframes rise{from{opacity:0;transform:translateY(-6px)}to{opacity:1;transform:none}}
.pending .lbl{font-family:var(--font-mono);font-size:.62rem;letter-spacing:.14em;
  text-transform:uppercase;color:var(--red);margin-bottom:.45rem}
.pending .t{font-size:1rem;font-weight:620;margin-bottom:.6rem}

.tasks{display:flex;flex-direction:column}
.task{display:flex;gap:.8rem;align-items:flex-start;padding:.75rem 0;
  border-bottom:1px solid var(--hairline)}
.task:last-child{border-bottom:none}
.task .box{width:15px;height:15px;border:1px solid var(--mute-dark);margin-top:.3rem;
  flex:0 0 15px;cursor:pointer;transition:.2s}
.task .box:hover{border-color:var(--red);background:rgba(226,59,34,.15)}
.task.done .box{background:var(--red);border-color:var(--red)}
.task.done .tt{color:var(--mute-dark);text-decoration:line-through}
.task .tb{flex:1;min-width:0}
.task .tt{font-size:.92rem;font-weight:500;line-height:1.4;word-break:break-word}
.task .tm{font-family:var(--font-mono);font-size:.66rem;letter-spacing:.05em;
  color:var(--mute-dark);margin-top:.25rem;display:flex;gap:.5rem;flex-wrap:wrap}
.task .x{font-size:.9rem;color:var(--mute-dark);padding:0 .2rem}
.task .x:hover{color:var(--red)}
.empty{padding:1.6rem .5rem;text-align:center;color:var(--mute-dark);
  font-family:var(--font-mono);font-size:.72rem;letter-spacing:.06em}

/* ---------- brief ---------- */
.brief{margin-top:.9rem;border:1px solid var(--hairline);background:var(--ink-3);
  padding:1rem 1.1rem;border-radius:2px;font-size:.88rem;line-height:1.65;
  white-space:pre-wrap;display:none;color:var(--copy)}
.brief.on{display:block;animation:rise .3s var(--ease-out)}
.brief b{color:var(--bone);font-weight:620}

/* ---------- toast ---------- */
#toast{position:fixed;left:50%;bottom:1.8rem;transform:translate(-50%,120%);
  background:var(--bone);color:var(--ink);padding:.75rem 1.3rem;border-radius:2px;
  font-family:var(--font-mono);font-size:.72rem;letter-spacing:.06em;
  opacity:0;transition:.35s var(--ease-out);pointer-events:none;z-index:60;
  max-width:88vw;text-align:center}
#toast.on{opacity:1;transform:translate(-50%,0)}

footer{margin-top:3rem;padding-top:1.4rem;border-top:1px solid var(--hairline);
  display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap;
  font-family:var(--font-mono);font-size:.66rem;letter-spacing:.08em;
  text-transform:uppercase;color:var(--mute-dark)}
footer .slash{color:var(--red)}
</style>
</head>
<body>
<div class="progress"><span id="bar"></span></div>

<div class="wrap">
  <nav>
    <div class="brand">
      Life<span class="slash">/</span>Pilot
      <small>S·/·S palette</small>
    </div>
    <div class="right">
      <span class="live"><i></i><span id="status">connecting</span></span>
      <span class="pill-link" style="color:var(--mute-dark)">demo console &middot; the room is the product</span>
      <button class="pill-link" id="notifyBtn" onclick="askNotify()">enable alerts</button>
      <a class="pill-link" href="/docs">API docs</a>
      <button class="pill-link" onclick="resetAll()">Reset</button>
    </div>
  </nav>

  <header class="hero">
    <div class="eyebrow"><span class="slash">/</span> Personal life operating system</div>
    <h1>Propose,<br>never <span class="red">presume.</span></h1>
    <p>Type the way you actually talk. LifePilot shows you <em>exactly what it understood</em> —
       and won't save a thing until you say yes.</p>
  </header>

  <div class="grid">
    <div>
      <div class="card">
        <div class="chead">
          <h2><span class="slash">/</span> Parse a sentence</h2>
          <span class="note" id="engineBadge" title="">RULES</span>
        </div>
        <textarea id="sentence" placeholder="urgent pay the electricity bill by Friday">urgent pay the electricity bill by Friday</textarea>
        <div class="row">
          <button class="btn btn-solid" id="parseBtn" onclick="parseSentence()">Parse <span class="btn-arrow">→</span></button>
          <button class="btn btn-ghost" onclick="document.getElementById('sentence').value='';">Clear</button>
          <button class="btn btn-ghost" id="micBtn" onclick="dictate('sentence')">&#9673; Speak</button>
        </div>
        <div class="chips" id="chips"></div>
        <div class="result" id="fields"></div>
        <div class="row" id="saveRow" style="display:none">
          <button class="btn btn-solid" id="saveParsedBtn" onclick="saveParsed()">Save this task <span class="btn-arrow">&rarr;</span></button>
          <span class="note" style="align-self:center">edits are allowed &middot; still nothing saved until you press</span>
        </div>
      </div>

      <div class="card">
        <div class="chead">
          <h2><span class="slash">/</span> Tasks</h2>
          <span class="note" id="taskCount">0 open</span>
        </div>
        <div class="tasks" id="tasks"><div class="empty">Nothing captured yet</div></div>
      </div>
    </div>

    <div>
      <div class="card">
        <div class="chead">
          <h2><span class="slash">/</span> Room</h2>
          <span class="note" id="noteState">propose → yes / no</span>
        </div>
        <div class="chat" id="chat"></div>
        <div class="chatinput">
          <input type="text" id="msg" placeholder="add a task to buy milk"
                 onkeydown="if(event.key==='Enter')sendMsg()">
          <button class="btn btn-ghost" id="micBtn2" onclick="dictate('msg')">&#9673;</button>
          <button class="btn btn-solid" id="sendBtn" onclick="sendMsg()">Send</button>
        </div>
        <div class="pending" id="pendingBox">
          <div class="lbl">Awaiting your approval · nothing saved</div>
          <div class="t" id="pendingTitle"></div>
          <div class="row" style="margin-top:0">
            <button class="btn btn-solid" id="saveBtn" onclick="confirmPending(true)">Save it</button>
            <button class="btn btn-ghost" id="discardBtn" onclick="confirmPending(false)">Discard</button>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="chead">
          <h2><span class="slash">/</span> Briefings</h2>
          <span class="note">read-only</span>
        </div>
        <div class="row" style="margin-top:0">
          <button class="btn btn-ghost" id="morningBtn" onclick="briefing('morning')">Morning</button>
          <button class="btn btn-ghost" id="eveningBtn" onclick="briefing('evening')">Evening</button>
          <button class="btn btn-ghost" id="planBtn" onclick="planDay()">Plan my day</button>
        </div>
        <div class="brief" id="brief"></div>
      </div>

      <div class="card">
        <div class="chead">
          <h2><span class="slash">/</span> Pushed to you</h2>
          <span class="note" id="pushChannel">outbox</span>
        </div>
        <div class="row" style="margin-top:0">
          <button class="btn btn-ghost" id="tickBtn" onclick="runTick()">Run scheduler now</button>
        </div>
        <div class="brief" id="pushLog"></div>
      </div>

      <div class="card">
        <div class="chead">
          <h2><span class="slash">/</span> Where it fails</h2>
          <span class="note">honest limits</span>
        </div>
        <div class="chips" id="fails" style="margin-top:0"></div>
        <div class="result" id="failFields" style="display:none"></div>
      </div>
    </div>
  </div>

  <footer>
    <span>LifePilot · local sqlite · no paid api <span class="slash">/</span> <span id="footStatus">live</span></span>
    <span>uvicorn backend.main:app</span>
  </footer>
</div>

<div id="toast"></div>

<script>
/* ------------------------------------------------------------------ utils */
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c =>
  ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

let toastTimer;
function toast(m){
  const t = $('toast'); t.textContent = m; t.classList.add('on');
  clearTimeout(toastTimer); toastTimer = setTimeout(()=>t.classList.remove('on'), 2600);
}

async function api(path, opts){
  const r = await fetch(path, Object.assign({headers:{'Content-Type':'application/json'}}, opts||{}));
  if(!r.ok){ let d=''; try{ d = await r.text(); }catch(e){} throw new Error(d || r.status); }
  return r.json();
}

/* ---------------------------------------------------------------- status */
async function checkHealth(){
  try{
    const h = await api('/health');
    $('status').textContent = 'backend live';
    const r = h.reminders || {};
    if(r.running){
      $('footStatus').textContent =
        'auto-reminders on · every ' + r.interval_seconds + 's · ' + r.total_sent + ' sent';
    } else {
      $('footStatus').textContent = 'auto-reminders OFF';
    }
  }catch(e){
    $('status').textContent = 'offline';
    $('footStatus').textContent = 'offline — start uvicorn';
  }
}

/* -------------------------------------------------------------- parsing */
const PRI = {1:'p1',2:'p2',3:''};
let lastParse = null;

function renderParse(data, target, readonly){
  const p = data.parsed, why = data.reasoning || {};
  lastParse = p;

  const editable = !readonly;
  const badge = $('engineBadge');
  if(badge && !readonly){
    const model = (data.engine || '').indexOf('model') === 0;
    badge.textContent = model ? 'MODEL' : 'RULES';
    badge.style.color = model ? 'var(--red)' : 'var(--mute)';
    badge.title = data.engine_note || '';
  }
  const rows = [
    ['title', editable
        ? '<input type="text" id="ed_title" value="'+esc(p.title)+'">'
        : '<div class="v">'+esc(p.title)+'</div>', why.title],
    ['category', editable
        ? '<select id="ed_category">'+Object.keys(CAT).map(c =>
            '<option'+(c===p.category?' selected':'')+'>'+c+'</option>').join('')+'</select>'
        : '<span class="tag">'+esc(p.category)+'</span>', why.category],
    ['priority', editable
        ? '<select id="ed_priority">'+[1,2,3].map(n =>
            '<option value="'+n+'"'+(n===p.priority?' selected':'')+'>priority '+n+'</option>').join('')+'</select>'
        : '<span class="tag '+(PRI[p.priority]||'')+'">priority '+p.priority+'</span>', why.priority],
    ['deadline', editable
        ? '<input type="date" id="ed_deadline" value="'+esc(p.deadline || '')+'">'
        : '<div class="v">'+esc(p.deadline || '\u2014 none \u2014')+'</div>', why.deadline],
    ['when', editable
        ? '<input type="time" id="ed_time" value="'+esc(p.suggested_time || '')+'">'
        : '<div class="v">'+esc(p.suggested_time || '\u2014 none \u2014')+'</div>', why.suggested_time],
    ['effort', editable
        ? '<input type="number" id="ed_minutes" min="1" value="'+p.estimated_minutes+'">'
        : '<div class="v">'+p.estimated_minutes+' min</div>', why.estimated_minutes],
  ];
  if(p.context){
    rows.push(['why', '<div class="v" style="color:var(--copy);font-weight:400">'+esc(p.context)+'</div>', '']);
  }

  target.innerHTML = rows.map(([k,v,w]) =>
    '<div class="field"><div class="k">'+k+'</div><div>'+v+
    (w ? '<div class="why">'+esc(w)+'</div>' : '')+'</div></div>').join('');

  $('saveRow').style.display = editable ? 'flex' : 'none';
}

async function parseSentence(){
  const text = $('sentence').value.trim();
  if(!text){ toast('Type a sentence first'); return; }
  const btn = $('parseBtn'); btn.disabled = true;
  try{
    const data = await api('/tasks/explain', {method:'POST', body: JSON.stringify({text})});
    renderParse(data, $('fields'));
  }catch(e){
    $('fields').innerHTML = '<div class="empty">Could not reach the backend — is uvicorn running?</div>';
  }finally{ btn.disabled = false; }
}

async function saveParsed(){
  if(!lastParse){ toast('Parse a sentence first'); return; }
  const btn = $('saveParsedBtn'); btn.disabled = true;
  const body = {
    title: $('ed_title').value.trim(),
    category: $('ed_category').value,
    priority: parseInt($('ed_priority').value, 10),
    deadline: $('ed_deadline').value || null,
    estimated_minutes: parseInt($('ed_minutes').value, 10) || 30,
    suggested_time: ($('ed_time') && $('ed_time').value) || null,
    context: lastParse.context || '',
    approved: true
  };
  try{
    const saved = await api('/tasks', {method:'POST', body: JSON.stringify(body)});
    toast('Saved: ' + saved.title);
    loadTasks();
  }catch(e){
    toast('Could not save');
  }finally{ btn.disabled = false; }
}

/* ---------------------------------------------------------------- chips */
const SAMPLES = [
  ['add a task to finish biology notes by Friday, high priority', true],
  ['urgent revise algebra today', true],
  ['pay electricity bill tomorrow', true],
  ['call the landlord about water', true],
  ['dentist appointment on monday', true],
  ['go to the gym for 45 minutes', true],
  ["mom's birthday is coming up, should think about a gift", false],
  ['the washing machine is making that noise again', false],
];
$('chips').innerHTML = SAMPLES.map(([s,good],i) =>
  '<button class="chip'+(good?'':' bad')+'" data-i="'+i+'">'+esc(s)+'</button>').join('');
document.querySelectorAll('#chips .chip').forEach(el => el.onclick = () => {
  $('sentence').value = SAMPLES[+el.dataset.i][0];
  parseSentence();
});

/* -------------------------------------------------------------- failures */
async function loadFails(){
  const bad = [
    "I really need to sort out that passport thing before the trip",
    "mom's birthday is coming up, should think about a gift",
  ];
  const out = [];
  for(const b of bad){
    try{ out.push(await api('/tasks/explain', {method:'POST', body: JSON.stringify({text:b})})); }catch(e){ return; }
  }
  $('fails').innerHTML = out.map((o,i) =>
    '<button class="chip bad" data-f="'+i+'">'+esc(o.input)+'</button>').join('');
  document.querySelectorAll('#fails .chip').forEach(el => el.onclick = () => {
    const el2 = $('failFields'); el2.style.display = 'block';
    renderParse(out[+el.dataset.f], el2, true);
  });
}

/* ----------------------------------------------------------------- tasks */
const CAT = {study:'study',personal:'personal',bill:'bill',health:'health',household:'household',work:'work'};

async function loadTasks(){
  try{
    const tasks = await api('/tasks');
    const open = tasks.filter(t => t.status === 'pending');
    $('taskCount').textContent = open.length + ' open · ' + tasks.length + ' total';
    if(!tasks.length){
      $('tasks').innerHTML = '<div class="empty">Nothing captured yet — try the room on the right</div>';
      return;
    }
    $('tasks').innerHTML = tasks.map(t => `
      <div class="task ${t.status === 'done' ? 'done' : ''}">
        <div class="box" onclick="completeTask(${t.id})" title="Mark done"></div>
        <div class="tb">
          <div class="tt">${esc(t.title)}</div>
          <div class="tm">
            <span>${esc(CAT[t.category] || t.category)}</span>
            <span>·</span><span>p${t.priority}</span>
            ${t.deadline ? '<span>·</span><span>'+esc(t.deadline)+'</span>' : ''}
            ${t.suggested_time ? '<span>·</span><span>at '+esc(t.suggested_time)+'</span>' : ''}
            <span>·</span><span>${t.estimated_minutes}m</span>
          </div>
        </div>
        <button class="x" onclick="deleteTask(${t.id})" title="Delete">×</button>
      </div>`).join('');
  }catch(e){
    $('tasks').innerHTML = '<div class="empty">Backend offline</div>';
  }
}

async function completeTask(id){
  await api('/tasks/'+id+'/complete', {method:'POST'});
  toast('Marked done'); loadTasks();
}
async function deleteTask(id){
  // Deleting is a change to stored data, so it needs an explicit yes.
  if(!confirm('Delete this task? This is the approval step.')) return;
  await api('/tasks/'+id+'?approved=true', {method:'DELETE'});
  toast('Deleted'); loadTasks();
}

/* ------------------------------------------------------------------ chat */
let sender = 'ui-' + Math.random().toString(36).slice(2, 8);

function bubble(text, kind, who){
  const d = document.createElement('div');
  d.className = 'msg ' + kind;
  d.innerHTML = (who ? '<span class="who">'+esc(who)+'</span>' : '') + esc(text);
  $('chat').appendChild(d);
  $('chat').scrollTop = $('chat').scrollHeight;
}

async function sendMsg(){
  const input = $('msg'); const m = input.value.trim();
  if(!m) return; input.value = '';
  bubble(m, 'user', 'You');
  try{
    const r = await api('/chat', {method:'POST', body: JSON.stringify({message:m, sender})});
    bubble(r.reply, 'bot', r.agent);
    await refreshPending();
    loadTasks();
  }catch(e){
    bubble('Backend unreachable. Start it with: uvicorn backend.main:app --reload', 'bot', 'System');
  }
}

async function refreshPending(){
  try{
    const r = await api('/chat/pending?sender=' + encodeURIComponent(sender));
    const box = $('pendingBox');
    if(r.pending){
      box.classList.add('on');
      $('pendingTitle').textContent = r.pending.summary;
      $('noteState').textContent = 'waiting on you';
    } else {
      box.classList.remove('on');
      $('noteState').textContent = 'propose → yes / no';
    }
  }catch(e){ /* ignore */ }
}

async function confirmPending(yes){
  try{
    const r = await api('/chat', {method:'POST', body: JSON.stringify({message: yes ? 'yes' : 'no', sender})});
    bubble(r.reply, 'bot', r.agent);
    $('pendingBox').classList.remove('on');
    loadTasks();
    toast(yes ? 'Saved' : 'Discarded');
  }catch(e){ toast('Could not confirm'); }
}

/* ------------------------------------------------------------- briefings */
async function briefing(which){
  try{
    const d = await api(which === 'morning' ? '/briefings/morning' : '/briefings/evening', {method:'POST'});
    const b = $('brief'); b.classList.add('on');
    b.textContent = d.message;
  }catch(e){ toast('Backend unreachable'); }
}

async function planDay(){
  const input = $('msg'); input.value = 'plan my day'; sendMsg();
}

async function resetAll(){
  if(!confirm('Delete all local tasks, bills and reminders?')) return;
  try{
    await api('/reset', {method:'POST'});
    toast('Cleared'); loadTasks(); refreshPending();
    $('brief').classList.remove('on');
  }catch(e){ toast('Could not reset'); }
}

/* ------------------------------------------------------------- push */
async function runTick(){
  const btn = $('tickBtn'); btn.disabled = true;
  try{
    const d = await api('/reminders/tick?force=true', {method:'POST'});
    const log = $('pushLog'); log.classList.add('on');
    if(!d.sent){
      log.textContent = 'Nothing to send right now.\\nThe scheduler remembers what it already sent today, so it stays quiet.';
    } else {
      log.textContent = d.sent + ' message(s) sent via ' + d.channel + ':\\n\\n' +
        d.messages.map(m => '\u2022 ' + m.text).join('\\n\\n');
    }
    $('pushChannel').textContent = d.channel;
  }catch(e){ toast('Backend unreachable'); }
  finally{ btn.disabled = false; }
}

async function loadHistory(){
  try{
    const rows = await api('/reminders/history?limit=5');
    if(rows.length) $('pushChannel').textContent = rows[0].channel || 'outbox';
  }catch(e){ /* ignore */ }
}

/* ------------------------------------------------------------- voice */
/* Speech goes through the browser, not the server: the transcript becomes
   text in the box, and from there it is the same proven path as typing.
   Speech recognition needs a real browser tab over http(s) — not file://,
   not a sandboxed preview frame. We say so instead of failing silently. */
let recogniser = null;
let listening = false;

function speechSupported(){
  return !!(window.SpeechRecognition || window.webkitSpeechRecognition);
}

function dictate(targetId){
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if(!SR){
    toast('This browser can\u2019t listen here. Type instead, or open the page in Chrome.');
    return;
  }
  const target = $(targetId);

  if(listening && recogniser){ recogniser.stop(); return; }

  try{
    recogniser = new SR();
  }catch(e){
    toast('Microphone unavailable. Type instead.');
    return;
  }
  recogniser.lang = 'en-US';
  recogniser.interimResults = true;
  recogniser.continuous = false;
  recogniser.maxAlternatives = 1;

  recogniser.onstart = () => {
    listening = true;
    const b = $('micBtn'); if(b) b.textContent = '\u25CF listening';
    target.placeholder = 'Listening\u2026 speak now';
  };
  recogniser.onresult = (event) => {
    let transcript = '';
    for(let i = event.resultIndex; i < event.results.length; i++){
      transcript += event.results[i][0].transcript;
    }
    target.value = transcript.trim();
  };
  recogniser.onerror = (event) => {
    const reasons = {
      'not-allowed': 'Microphone permission was blocked.',
      'no-speech': 'I didn\u2019t hear anything.',
      'audio-capture': 'No microphone found.',
      'network': 'Speech needs a network connection in this browser.',
      'service-not-allowed': 'This page can\u2019t reach the speech service.'
    };
    toast(reasons[event.error] || ('Could not listen: ' + event.error));
  };
  recogniser.onend = () => {
    listening = false;
    const b = $('micBtn'); if(b) b.textContent = '\u25CF Speak';
    target.placeholder = targetId === 'sentence'
      ? 'urgent pay the electricity bill by Friday'
      : 'add a task to buy milk';
    if(target.value.trim()) target.focus();
  };

  try{ recogniser.start(); }
  catch(e){ toast('Could not start listening. Type instead.'); }
}

/* ------------------------------------------------------- notifications */
/* Optional desktop alerts. They need a real browser tab and permission; the
   server has no way to push to you on its own. If this is unsupported, we
   say so rather than pretending it worked. */
let seenDeliveryCount = null;

function askNotify(){
  if(!('Notification' in window)){
    toast('This browser has no desktop notifications. Try Chrome or Edge.');
    return;
  }
  if(Notification.permission === 'granted'){
    toast('Alerts are already on.');
    return;
  }
  Notification.requestPermission().then(perm => {
    if(perm === 'granted'){ toast('Alerts on. Reminders will pop up while this tab is open.'); }
    else { toast('Alerts blocked. The reminders still go to the outbox.'); }
  }).catch(() => toast('Could not ask for notification permission.'));
}

async function pollDeliveries(){
  if(!('Notification' in window) || Notification.permission !== 'granted') return;
  try{
    const rows = await api('/reminders/history?limit=20');
    const count = rows.length;
    if(seenDeliveryCount === null){ seenDeliveryCount = count; return; }
    if(count > seenDeliveryCount){
      const fresh = rows.slice(0, count - seenDeliveryCount);
      seenDeliveryCount = count;
      fresh.forEach(r => {
        try{
          new Notification('LifePilot', {body: r.text.split('\\n')[0], tag: r.kind + r.id});
        }catch(e){ /* some browsers require a service worker; ignore */ }
      });
      loadHistory();
      loadTasks();
    }
  }catch(e){ /* offline; try again next poll */ }
}

/* ---------------------------------------------------------------- boot */
$('chat').innerHTML = '<div class="msg sys">Connected to the live backend. Everything here hits the real API.</div>';

document.addEventListener('scroll', () => {
  const h = document.documentElement;
  const p = h.scrollTop / Math.max(1, h.scrollHeight - h.clientHeight);
  $('bar').style.transform = 'scaleX(' + p + ')';
}, {passive:true});

checkHealth();
parseSentence();
loadTasks();
refreshPending();
loadFails();
loadHistory();
setInterval(checkHealth, 15000);
setInterval(pollDeliveries, 20000);
pollDeliveries();
</script>
</body>
</html>
"""


def render_ui() -> str:
    """Return the complete LifePilot UI."""
    return PAGE
