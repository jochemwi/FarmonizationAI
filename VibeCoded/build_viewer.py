"""Build one HTML page that shows the actions of one or more runs.

Input:  one or more actions JSON files from trace_actions.py.
Output: a single self-contained HTML file (open it in a browser).

Example:
    python build_viewer.py observability/actions_*.json -o observability/viewer.html
"""
import argparse
import json
import re
from pathlib import Path

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Action trace viewer</title>
</head><body>
__BODY__
</body></html>
"""

TEMPLATE = r"""<title>Action Trace Viewer</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400&display=swap">
<style>
/* Layout: one column; a proportional time strip on top, then an accordion of actions; each action opens into a staircase of calls. */
:root{
  --bg:#f6f7f9; --panel:#ffffff; --fg:#1c2128; --muted:#5d6672; --line:#d9dde3; --line-strong:#b9c0ca; --code-bg:#eef0f3;
  --focus:#2b5fd9;
  --k-question:#c47a0a; --k-validate:#0f8a6a; --k-build:#c2475f; --k-explore:#5d6f8a; --k-final:#6a5acd;
  --font-body:"Inter",system-ui,-apple-system,"Segoe UI",sans-serif; --font-mono:"JetBrains Mono",ui-monospace,Menlo,Consolas,monospace;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --bg:#15181d; --panel:#1d2128; --fg:#e6e9ee; --muted:#9aa4b2; --line:#303640; --line-strong:#454d5a; --code-bg:#12151a;
  --focus:#7aa2ff;
  --k-question:#e0a23f; --k-validate:#3fc3a0; --k-build:#e5758a; --k-explore:#8ea3c2; --k-final:#9d8df0; color-scheme:dark}}
:root[data-theme="dark"]{
  --bg:#15181d; --panel:#1d2128; --fg:#e6e9ee; --muted:#9aa4b2; --line:#303640; --line-strong:#454d5a; --code-bg:#12151a;
  --focus:#7aa2ff;
  --k-question:#e0a23f; --k-validate:#3fc3a0; --k-build:#e5758a; --k-explore:#8ea3c2; --k-final:#9d8df0; color-scheme:dark}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--fg);font-family:var(--font-body);font-size:14px;line-height:1.5;
  padding-block:24px 48px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
.wrap{max-width:960px;margin:0 auto;display:flex;flex-direction:column;gap:20px;min-width:0}
h1{font-size:22px;font-weight:600;margin:0;letter-spacing:-0.01em;text-wrap:balance}
.lede{margin:4px 0 0;color:var(--muted);max-width:70ch}
.bar{display:flex;flex-wrap:wrap;gap:12px 20px;align-items:center}
.seg{display:inline-flex;border:1px solid var(--line-strong);border-radius:8px;overflow:hidden;background:var(--panel)}
.seg button{all:unset;cursor:pointer;padding:6px 14px;font-size:13px;color:var(--muted)}
.seg button[aria-pressed="true"]{background:var(--fg);color:var(--bg)}
.seg button:focus-visible,.chip:focus-visible,.row-head:focus-visible,.it-head:focus-visible,.link:focus-visible{outline:2px solid var(--focus);outline-offset:2px}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{all:unset;cursor:pointer;display:inline-flex;align-items:center;gap:6px;padding:3px 10px;border:1px solid var(--line-strong);border-radius:999px;font-size:12px;color:var(--muted);background:var(--panel)}
.chip[aria-pressed="true"]{color:var(--fg);border-color:var(--fg)}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block;flex:none}
.link{all:unset;cursor:pointer;font-size:12px;color:var(--muted);text-decoration:underline;text-underline-offset:3px}
.sum{display:flex;flex-wrap:wrap;gap:4px 24px;color:var(--muted);font-size:13px;font-variant-numeric:tabular-nums}
.sum b{color:var(--fg);font-weight:500}
.strip{display:flex;height:22px;gap:1px;border-radius:5px;overflow:hidden;background:var(--line)}
.strip button{all:unset;cursor:pointer;min-width:2px;height:100%;opacity:.9}
.strip button:hover,.strip button:focus-visible{opacity:1;outline:2px solid var(--fg);outline-offset:-2px}
.strip-note{font-size:12px;color:var(--muted);margin-top:-12px}
.list{display:flex;flex-direction:column;gap:10px;min-width:0}
.row{background:var(--panel);border:1px solid var(--line);border-radius:8px;min-width:0}
.row-head{all:unset;box-sizing:border-box;cursor:pointer;display:grid;grid-template-columns:112px minmax(0,1fr) 20px;gap:4px 14px;align-items:start;width:100%;padding:12px 14px}
.row-no{font-weight:500;font-variant-numeric:tabular-nums}
.row-kind{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--muted);margin-top:2px}
.row-title{border:1px solid var(--line-strong);border-radius:8px;padding:7px 12px;overflow-wrap:anywhere;background:var(--bg)}
.row-meta{font-size:12px;color:var(--muted);margin-top:4px;font-variant-numeric:tabular-nums}
.chev{width:14px;height:14px;margin-top:8px;color:var(--muted);transition:transform .15s;justify-self:end;transform:rotate(90deg)}
.row.open>.row-head .chev{transform:none}
@media (prefers-reduced-motion:reduce){.chev{transition:none}}
.row-body{display:none;padding:2px 14px 14px 14px;border-top:1px solid var(--line)}
.row.open>.row-body{display:block}
.it{margin-top:10px;min-width:0}
.it-head{all:unset;box-sizing:border-box;cursor:pointer;display:flex;gap:10px;align-items:baseline;width:100%;padding:4px 0;font-size:13px}
.it-head .n{color:var(--muted);font-variant-numeric:tabular-nums;flex:none;width:46px}
.it-head .t{flex:1;min-width:0;overflow-wrap:anywhere}
.it-head .d{color:var(--muted);font-variant-numeric:tabular-nums;flex:none}
.it-head .chev{margin-top:0;align-self:center}
.it.open>.it-head .chev{transform:none}
.it-body{display:none;padding:6px 0 4px 0}
.it.open>.it-body{display:block}
.pair{margin:0 0 10px;min-width:0}
.d1{margin-left:28px}.d2{margin-left:56px}
.box{border:1px solid var(--line-strong);border-radius:8px;overflow:hidden;background:var(--bg);min-width:0}
.box-h{display:flex;flex-wrap:wrap;gap:2px 10px;justify-content:space-between;align-items:center;padding:5px 10px;font-size:12px;font-weight:500;border-bottom:1px solid var(--line);background:var(--panel)}
.box-h span:last-child{font-weight:400;color:var(--muted);font-variant-numeric:tabular-nums}
.box-b{padding:8px 10px;font-size:13px;overflow-wrap:anywhere}
.box-b p{margin:0 0 6px}
.box-b p:last-child{margin-bottom:0}
pre{margin:6px 0 0;padding:8px 10px;background:var(--code-bg);border-radius:6px;font-family:var(--font-mono);font-size:12px;line-height:1.5;white-space:pre-wrap;overflow-wrap:anywhere;max-height:220px;overflow:auto}
.tags{display:flex;flex-wrap:wrap;gap:4px;margin-top:6px}
.tag{font-size:11px;color:var(--muted);border:1px solid var(--line);border-radius:4px;padding:0 6px}
.q{font-style:normal;border-left:2px solid var(--line-strong);padding-left:10px;margin:0 0 6px;white-space:pre-wrap}
.empty{color:var(--muted);padding:24px 0}
.foot{font-size:12px;color:var(--muted);max-width:80ch}
@media (max-width:560px){
  .row-head{grid-template-columns:minmax(0,1fr) 20px}
  .row-lbl{grid-column:1/2}.row-main{grid-column:1/2}
  .row-head .chev{grid-column:2;grid-row:1}
  .d1{margin-left:14px}.d2{margin-left:28px}
}
</style>

<div class="wrap">
  <header>
    <h1>Action trace viewer</h1>
    <p class="lede">The steps of one harmonization run, grouped into actions. Each action closes when the agent runs the validator, runs the build script, asks a human, or gives its final answer. Open an action to see its steps, and a step to see the model call and the command behind it.</p>
  </header>

  <div class="bar">
    <div class="seg" role="group" aria-label="Run" id="runs"></div>
    <div class="chips" role="group" aria-label="Filter by kind" id="kinds"></div>
    <button class="link" id="collapse" type="button">Collapse all</button>
  </div>

  <div class="sum" id="sum"></div>
  <div>
    <div class="strip" id="strip" role="group" aria-label="Actions on a time axis"></div>
  </div>
  <div class="strip-note" id="stripnote"></div>

  <div class="list" id="list"></div>
  <p class="foot">Built from Langfuse observations with trace_actions.py. An action title is the description the agent gave its closing bash call, and a question action shows the question text. The kind comes from the closing call. The grouping is a heuristic; it needs no change to the harness.</p>
</div>

<script type="application/json" id="data">__DATA__</script>
<script>
(function(){
  var DATA = JSON.parse(document.getElementById('data').textContent);
  var KINDS = [['question','Question'],['validate','Validate'],['build','Build script'],['explore','Explore'],['final','Final answer']];
  var KIND_LABEL = {}; KINDS.forEach(function(k){KIND_LABEL[k[0]]=k[1];});
  var state = {run:Object.keys(DATA)[0], kinds:{question:true,validate:true,build:true,explore:true,final:true}};
  var openRows = {};

  function el(tag, cls, text){var e=document.createElement(tag); if(cls)e.className=cls; if(text!=null)e.textContent=text; return e;}
  function dot(kind){var d=el('span','dot'); d.style.background='var(--k-'+kind+')'; return d;}
  function fmt(s){s=Math.round(s); if(s<60) return s+' s'; var m=Math.floor(s/60), r=s%60; return m+' min'+(r?' '+r+' s':'');}
  function kfmt(n){return n>=1000?(n/1000).toFixed(1)+'k':String(n);}
  function chevron(){
    var s=document.createElementNS('http://www.w3.org/2000/svg','svg');
    s.setAttribute('viewBox','0 0 14 14'); s.setAttribute('class','chev'); s.setAttribute('aria-hidden','true');
    var p=document.createElementNS('http://www.w3.org/2000/svg','path');
    p.setAttribute('d','M3 5l4 4 4-4'); p.setAttribute('fill','none'); p.setAttribute('stroke','currentColor'); p.setAttribute('stroke-width','1.6'); p.setAttribute('stroke-linecap','round'); p.setAttribute('stroke-linejoin','round');
    s.appendChild(p); return s;
  }
  function toggle(node, head){var o=node.classList.toggle('open'); head.setAttribute('aria-expanded', o?'true':'false'); return o;}

  function box(label, meta, body){
    var b=el('div','box'), h=el('div','box-h'); h.appendChild(el('span',null,label)); h.appendChild(el('span',null,meta||''));
    b.appendChild(h); var bb=el('div','box-b'); body(bb); b.appendChild(bb); return b;
  }
  function pair(depth, a, b){var p=el('div','pair d'+depth); p.appendChild(a); p.appendChild(el('div')).style.height='6px'; p.appendChild(b); return p;}
  function code(text){var p=el('pre'); p.textContent=text; return p;}

  function iteration(it){
    var wrap=el('div','it'), head=el('button','it-head'); head.type='button'; head.setAttribute('aria-expanded','false');
    var title = it.question ? 'Asks the human' : (it.tool ? it.tool.description : 'Final answer');
    var dur = it.question ? it.llm.dur_s + it.wait_s : it.llm.dur_s + (it.tool?it.tool.dur_s:0);
    head.appendChild(el('span','n','#'+it.n)); head.appendChild(el('span','t',title)); head.appendChild(el('span','d',fmt(dur))); head.appendChild(chevron());
    var body=el('div','it-body');

    body.appendChild(pair(0,
      box('LLM call', fmt(it.llm.dur_s)+' · '+kfmt(it.llm.in_tokens)+' in, '+kfmt(it.llm.out_tokens)+' out', function(b){ b.appendChild(el('p',null,'Model call')); b.firstChild.style.color='var(--muted)'; }),
      box('Generation', '$'+it.llm.cost_usd.toFixed(3), function(b){
        b.appendChild(el('p',null,it.llm.text||'No text in this generation.'));
        if(it.llm.reasoning&&it.llm.reasoning.length){var t=el('div','tags'); it.llm.reasoning.forEach(function(r){t.appendChild(el('span','tag',r));}); b.appendChild(t);}
      })));
    if(it.question){
      body.appendChild(pair(1,
        box('Tool call', '', function(b){b.appendChild(el('p',null,'ask_human')); b.firstChild.style.color='var(--muted)';}),
        box('Ask human', 'waited '+fmt(it.wait_s), function(b){b.appendChild(el('p','q',it.question));})));
    } else if(it.tool){
      var isBuild = it.tool.category==='build script';
      body.appendChild(pair(1,
        box('Tool call', fmt(it.tool.dur_s), function(b){b.appendChild(el('p',null,it.tool.name)); b.firstChild.style.color='var(--muted)';}),
        box('Bash …', it.tool.category, function(b){
          b.appendChild(el('p',null,it.tool.description));
          if(!isBuild) b.appendChild(code(it.tool.command));
          if(it.tool.output) b.appendChild(code(it.tool.output));
        })));
      if(isBuild){
        body.appendChild(pair(2,
          box('Code generation', '', function(b){b.appendChild(el('p',null,'Writes or runs the build script')); b.firstChild.style.color='var(--muted)';}),
          box('build.py edit', '', function(b){b.appendChild(code(it.tool.command));})));
      }
    }
    head.addEventListener('click',function(){toggle(wrap,head);});
    wrap.appendChild(head); wrap.appendChild(body); return wrap;
  }

  function row(a){
    var r=el('div','row'), head=el('button','row-head'); head.type='button';
    var open=!!openRows[state.run+a.id]; if(open) r.classList.add('open'); head.setAttribute('aria-expanded',open?'true':'false'); r.id='a'+a.id;
    var lbl=el('div','row-lbl'); lbl.appendChild(el('div','row-no','Action #'+a.id));
    var k=el('div','row-kind'); k.appendChild(dot(a.kind)); k.appendChild(document.createTextNode(KIND_LABEL[a.kind])); lbl.appendChild(k);
    var main=el('div','row-main'); main.appendChild(el('div','row-title',a.title));
    var meta=a.iterations.length+(a.iterations.length===1?' step':' steps')+' · '+fmt(a.dur_s)+(a.wait_s?' · '+fmt(a.wait_s)+' waiting for a human':'')+' · starts at '+a.start_min.toFixed(1)+' min';
    main.appendChild(el('div','row-meta',meta));
    head.appendChild(lbl); head.appendChild(main); head.appendChild(chevron());
    var body=el('div','row-body');
    a.iterations.forEach(function(it){body.appendChild(iteration(it));});
    head.addEventListener('click',function(){var o=toggle(r,head); openRows[state.run+a.id]=o;});
    r.appendChild(head); r.appendChild(body); return r;
  }

  function render(){
    var run=DATA[state.run], acts=run.actions;
    var shown=acts.filter(function(a){return state.kinds[a.kind];});
    var tot={q:0,wait:0,steps:0}; acts.forEach(function(a){tot.steps+=a.iterations.length; tot.wait+=a.wait_s; if(a.kind==='question')tot.q++;});
    var sum=document.getElementById('sum'); sum.textContent='';
    [['Duration',run.duration_min.toFixed(1)+' min'],['Actions',String(acts.length)],['Steps',String(tot.steps)],['Questions',String(tot.q)],['Waiting for a human',fmt(tot.wait)]].forEach(function(p){
      var s=el('span'); s.appendChild(document.createTextNode(p[0]+' ')); s.appendChild(el('b',null,p[1])); sum.appendChild(s);});
    var strip=document.getElementById('strip'); strip.textContent='';
    acts.forEach(function(a){
      var b=el('button'); b.type='button'; b.style.flex=String(Math.max(a.dur_s,3))+' 1 0'; b.style.background='var(--k-'+a.kind+')';
      b.title='Action #'+a.id+': '+a.title; b.setAttribute('aria-label','Action '+a.id+', '+KIND_LABEL[a.kind]+', '+fmt(a.dur_s));
      if(!state.kinds[a.kind]) b.style.opacity='.25';
      b.addEventListener('click',function(){
        state.kinds[a.kind]=true; syncChips(); renderList();
        var r=document.getElementById('a'+a.id); if(r){ if(!r.classList.contains('open')) r.querySelector('.row-head').click(); r.scrollIntoView({block:'center'}); }
      });
      strip.appendChild(b);
    });
    document.getElementById('stripnote').textContent='Each block is one action, as wide as it took. Click a block to jump to it.';
    renderList();
  }
  function renderList(){
    var acts=DATA[state.run].actions.filter(function(a){return state.kinds[a.kind];});
    var list=document.getElementById('list'); list.textContent='';
    if(!acts.length){list.appendChild(el('div','empty','No actions match the selected kinds.')); return;}
    acts.forEach(function(a){list.appendChild(row(a));});
  }
  function syncChips(){document.querySelectorAll('#kinds .chip').forEach(function(c){c.setAttribute('aria-pressed',state.kinds[c.dataset.k]?'true':'false');});}

  var runs=document.getElementById('runs');
  Object.keys(DATA).forEach(function(name){
    var b=el('button',null,name); b.type='button'; b.setAttribute('aria-pressed',name===state.run?'true':'false');
    b.addEventListener('click',function(){state.run=name; runs.querySelectorAll('button').forEach(function(x){x.setAttribute('aria-pressed',x===b?'true':'false');}); try{history.replaceState(null,'','#'+name.toLowerCase());}catch(e){} firstOpen(); render();});
    runs.appendChild(b);
  });
  var kinds=document.getElementById('kinds');
  KINDS.forEach(function(k){
    var c=el('button','chip'); c.type='button'; c.dataset.k=k[0]; c.appendChild(dot(k[0])); c.appendChild(document.createTextNode(k[1]));
    c.addEventListener('click',function(){state.kinds[k[0]]=!state.kinds[k[0]]; syncChips(); render();});
    kinds.appendChild(c);
  });
  document.getElementById('collapse').addEventListener('click',function(){openRows={}; renderList();});
  function firstOpen(){
    var q=DATA[state.run].actions.filter(function(a){return a.kind==='question';})[0];
    var any=Object.keys(openRows).some(function(k){return k.indexOf(state.run)===0;});
    if(q && !any){openRows[state.run+q.id]=true;}
  }
  var h=(location.hash||'').replace('#','').toLowerCase();
  Object.keys(DATA).forEach(function(n){if(n.toLowerCase()===h)state.run=n;});
  runs.querySelectorAll('button').forEach(function(x){x.setAttribute('aria-pressed',x.textContent===state.run?'true':'false');});
  syncChips(); firstOpen(); render();
})();
</script>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("actions", nargs="+", help="actions JSON files")
    ap.add_argument("-o", "--out", default="viewer.html")
    args = ap.parse_args()

    data = {}
    for name in args.actions:
        data.update(json.load(open(name, encoding="utf-8")))
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--")

    body = TEMPLATE.replace("__DATA__", payload)
    body = re.sub(r'<meta name="claude:[^>]*>\n?', "", body)
    body = re.sub(r"<title>.*?</title>\n?", "", body)
    Path(args.out).write_text(PAGE.replace("__BODY__", body), encoding="utf-8")
    print(f"{len(data)} run(s): {', '.join(data)}")
    print(f"saved {args.out}")


if __name__ == "__main__":
    main()
