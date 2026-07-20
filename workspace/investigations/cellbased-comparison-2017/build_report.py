"""Generate the read-only investigation workbench for cellbased-comparison-2017.

Reads the investigation + study YAMLs and both fractional-length baselines
(cbc-01 C++ ground truth, cbc-04 PyChaste reproduction) and emits a single
self-contained HTML page: verdict, reproducibility scorecard, an interactive
C++-vs-PyChaste trajectory overlay (Plotly), per-study cards with reproducibility
metrics, methodology, and limitations.

Regenerate:  python workspace/investigations/cellbased-comparison-2017/build_report.py
Output:      workspace/investigations/cellbased-comparison-2017/report.html
"""
import base64
import html
import json
import os
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, REPO)
from pbg_chaste.sorting_analysis import load_source  # noqa: E402

STUDIES = ["cbc-01-cxx-reference-baseline", "cbc-02-onlattice-wrapper-extension",
           "cbc-03-random-motion-equivalence", "cbc-04-cell-sorting-reproduction"]
MODEL_LABEL = {"ca": "CA", "cp": "CP", "os": "OS", "vt": "VT", "vm": "VM"}
MODEL_NAME = {"ca": "Cellular automaton", "cp": "Cellular Potts",
              "os": "Overlapping spheres", "vt": "Voronoi tessellation",
              "vm": "Vertex model"}
VERDICT_CLASS = {"match": "ok", "close": "ok", "partial": "warn", "blocked": "bad"}


def load_yaml(p):
    with open(p) as f:
        return yaml.safe_load(f)


def esc(s):
    return html.escape(str(s)) if s is not None else ""


def trajectories():
    """Both sources, normalized to the value at labelling (t=10), as Plotly traces."""
    cxx_root = os.path.join(HERE, "studies", STUDIES[0], "cxx-baseline")
    pyc_root = os.path.join(HERE, "studies", STUDIES[3], "pychaste-baseline")
    cxx = load_source(cxx_root, "cxx")
    pyc = load_source(pyc_root, "pychaste")

    def norm(tr):
        base = tr.at(10.0) or next((x for x in tr.fractional_length if x), 1.0)
        xs, ys = [], []
        for t, v in zip(tr.times, tr.fractional_length):
            if v is None:
                continue
            xs.append(t)
            ys.append(v / base if base else v)
        return xs, ys

    data = {}
    for m in ("ca", "cp", "os", "vt", "vm"):
        data[m] = {"cxx": None, "pyc": None}
        if m in cxx:
            x, y = norm(cxx[m])
            data[m]["cxx"] = {"x": x, "y": y}
        if m in pyc:
            x, y = norm(pyc[m])
            data[m]["pyc"] = {"x": x, "y": y}
    return data


def scorecard_rows():
    cbc04 = load_yaml(os.path.join(HERE, "studies", STUDIES[3], "study.yaml"))
    rows = []
    for m in cbc04["reproducibility_metrics"]["metrics"]:
        if m["observable"] != "fractional_boundary_length":
            continue
        rows.append(m)
    return rows


def render():
    inv = load_yaml(os.path.join(HERE, "investigation.yaml"))
    ex = inv.get("executive", {})
    traj = trajectories()
    rows = scorecard_rows()

    # --- reproducibility scorecard table ---
    order = ["vm", "cp", "vt", "os", "ca"]
    rows_by_model = {r["model"]: r for r in rows}
    sc = []
    for m in order:
        r = rows_by_model.get(m)
        if not r:
            continue
        v = r["verdict"]
        tv = r.get("tutorial_value")
        rv = r.get("reproduction_value")
        md = r.get("max_abs_divergence")
        sc.append(f"""<tr>
          <td><b>{MODEL_LABEL[m]}</b> <span class="mut">{MODEL_NAME[m]}</span></td>
          <td class="num">{'—' if tv is None else f'{tv:.3f}'}</td>
          <td class="num">{'—' if rv is None else f'{rv:.3f}'}</td>
          <td class="num">{'—' if md is None else f'{md:.3f}'}</td>
          <td><span class="pill {VERDICT_CLASS[v]}">{esc(v)}</span></td>
          <td class="note">{esc(r.get('note',''))}</td>
        </tr>""")

    # --- per-study cards ---
    cards = []
    for slug in STUDIES:
        s = load_yaml(os.path.join(HERE, "studies", slug, "study.yaml"))
        rm = s.get("reproducibility_metrics", {})
        conf = s.get("confidence", "—")
        metric_rows = ""
        for mt in rm.get("metrics", []):
            v = mt.get("verdict", "")
            metric_rows += f"""<tr>
              <td>{esc(mt.get('observable'))} <span class="mut">{esc(mt.get('model',''))}</span></td>
              <td class="num">{esc(mt.get('tutorial_value'))}</td>
              <td class="num">{esc(mt.get('reproduction_value'))}</td>
              <td><span class="pill {VERDICT_CLASS.get(v,'warn')}">{esc(v)}</span></td>
            </tr>"""
        cards.append(f"""<div class="card">
          <div class="card-h">
            <h3>{esc(s.get('title', slug))}</h3>
            <span class="pill {'ok' if conf=='Accepted' else 'warn'}">{esc(conf)}</span>
          </div>
          <p class="q">{esc((s.get('question') or '').strip())}</p>
          <p class="claim">{esc((s.get('claim') or '').strip())}</p>
          <table class="mini"><thead><tr><th>observable</th><th>tutorial</th><th>ours</th><th>verdict</th></tr></thead>
          <tbody>{metric_rows}</tbody></table>
        </div>""")

    # embed the figure as a data URI so the report is fully self-contained and
    # can be served from any path (gh-pages, local file, repo browse)
    figpath = os.path.join(HERE, "studies", STUDIES[3], "fractional_length.png")
    with open(figpath, "rb") as f:
        figrel = "data:image/png;base64," + base64.b64encode(f.read()).decode()

    doc = f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Reproducing Osborne et al. 2017 · pbg-chaste workbench</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
:root{{
  --bg:#f6f7f9; --panel:#ffffff; --fg:#182230; --mut:#5b6b7c; --line:#e3e8ee;
  --accent:#2f6f8f; --cxx:#1f77b4; --pyc:#d62728;
  --ok-bg:#e7f6ec; --ok-fg:#1a7f42; --warn-bg:#fdf1dc; --warn-fg:#9a6700;
  --bad-bg:#fbe9e9; --bad-fg:#a3282a;
}}
@media (prefers-color-scheme:dark){{
  :root{{
    --bg:#0f141a; --panel:#161d26; --fg:#e6ecf2; --mut:#93a2b3; --line:#26313d;
    --accent:#6cb6d6; --cxx:#5aa9d6; --pyc:#f2726f;
    --ok-bg:#12301f; --ok-fg:#5fd08a; --warn-bg:#33280f; --warn-fg:#e2b24d;
    --bad-bg:#341a1b; --bad-fg:#ef8785;
  }}
}}
:root[data-theme="dark"]{{
  --bg:#0f141a; --panel:#161d26; --fg:#e6ecf2; --mut:#93a2b3; --line:#26313d;
  --accent:#6cb6d6; --cxx:#5aa9d6; --pyc:#f2726f;
  --ok-bg:#12301f; --ok-fg:#5fd08a; --warn-bg:#33280f; --warn-fg:#e2b24d;
  --bad-bg:#341a1b; --bad-fg:#ef8785;
}}
:root[data-theme="light"]{{
  --bg:#f6f7f9; --panel:#ffffff; --fg:#182230; --mut:#5b6b7c; --line:#e3e8ee;
  --accent:#2f6f8f; --cxx:#1f77b4; --pyc:#d62728;
  --ok-bg:#e7f6ec; --ok-fg:#1a7f42; --warn-bg:#fdf1dc; --warn-fg:#9a6700;
  --bad-bg:#fbe9e9; --bad-fg:#a3282a;
}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--fg);line-height:1.6;
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;}}
.wrap{{max-width:1080px;margin:0 auto;padding:0 24px}}
header{{padding:56px 0 12px}}
.eyebrow{{text-transform:uppercase;letter-spacing:.12em;font-size:.74rem;color:var(--accent);font-weight:700}}
h1{{font-size:2.15rem;line-height:1.15;margin:.35rem 0 .5rem;text-wrap:balance;
  font-family:Georgia,'Iowan Old Style','Times New Roman',serif;font-weight:600}}
.lede{{color:var(--mut);font-size:1.06rem;max-width:70ch}}
.chips{{margin-top:18px;display:flex;gap:10px;flex-wrap:wrap}}
.chip{{background:var(--panel);border:1px solid var(--line);border-radius:999px;
  padding:6px 14px;font-size:.82rem;color:var(--mut)}}
.chip b{{color:var(--fg)}}
.verdict{{background:var(--panel);border:1px solid var(--line);border-left:4px solid var(--accent);
  border-radius:12px;padding:22px 24px;margin:26px 0 8px}}
.verdict h2{{margin:0 0 8px;font-size:1.05rem;letter-spacing:.02em}}
.verdict p{{margin:0;color:var(--fg);max-width:78ch}}
section{{padding:34px 0;border-top:1px solid var(--line);margin-top:14px}}
h2.sec{{font-family:Georgia,serif;font-size:1.5rem;margin:0 0 4px}}
.sub{{color:var(--mut);margin:0 0 18px;max-width:74ch}}
table{{width:100%;border-collapse:collapse;font-size:.9rem}}
.scorecard{{background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden}}
.scorecard th,.scorecard td{{padding:11px 14px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}}
.scorecard th{{font-size:.72rem;text-transform:uppercase;letter-spacing:.06em;color:var(--mut);font-weight:700}}
.scorecard tr:last-child td{{border-bottom:none}}
td.num{{font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap}}
td.note{{color:var(--mut);font-size:.83rem;max-width:34ch}}
.mut{{color:var(--mut);font-weight:400;font-size:.9em}}
.pill{{display:inline-block;padding:2px 10px;border-radius:999px;font-size:.76rem;font-weight:700}}
.pill.ok{{background:var(--ok-bg);color:var(--ok-fg)}}
.pill.warn{{background:var(--warn-bg);color:var(--warn-fg)}}
.pill.bad{{background:var(--bad-bg);color:var(--bad-fg)}}
#overlay{{width:100%;height:340px}}
.legend{{display:flex;gap:20px;margin:8px 2px 0;font-size:.82rem;color:var(--mut);flex-wrap:wrap}}
.legend i{{display:inline-block;width:22px;height:0;border-top-width:3px;border-top-style:solid;vertical-align:middle;margin-right:6px}}
.cards{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
@media(max-width:780px){{.cards{{grid-template-columns:1fr}}}}
.card{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px 20px}}
.card-h{{display:flex;justify-content:space-between;align-items:center;gap:10px}}
.card h3{{margin:0;font-size:1.02rem}}
.card .q{{color:var(--mut);font-size:.86rem;margin:.5rem 0}}
.card .claim{{font-size:.92rem;margin:.4rem 0 .8rem}}
table.mini{{font-size:.8rem}}
table.mini th{{text-align:left;color:var(--mut);font-weight:600;padding:4px 8px 4px 0;border-bottom:1px solid var(--line)}}
table.mini td{{padding:4px 8px 4px 0;border-bottom:1px solid var(--line)}}
table.mini td.num{{text-align:left}}
figure{{margin:0}}
figure img{{width:100%;border:1px solid var(--line);border-radius:10px;background:#fff}}
figcaption{{color:var(--mut);font-size:.82rem;margin-top:8px}}
ul.tight{{max-width:78ch}} ul.tight li{{margin:.35rem 0}}
code{{font-family:ui-monospace,'SF Mono',Menlo,Consolas,monospace;font-size:.86em;
  background:color-mix(in srgb,var(--mut) 16%,transparent);padding:1px 5px;border-radius:5px}}
footer{{padding:30px 0 60px;color:var(--mut);font-size:.84rem}}
a{{color:var(--accent)}}
.toggle{{position:fixed;top:14px;right:16px;background:var(--panel);border:1px solid var(--line);
  color:var(--mut);border-radius:8px;padding:6px 10px;font-size:.8rem;cursor:pointer;z-index:20}}
</style></head><body>
<button class="toggle" onclick="tt()">◐ theme</button>
<div class="wrap">
<header>
  <div class="eyebrow">pbg-chaste · investigation workbench · read-only</div>
  <h1>{esc(inv.get('title'))}</h1>
  <p class="lede">{esc(ex.get('what_is_this','').strip())}</p>
  <div class="chips">
    <span class="chip">Paper · <b>Osborne et al. 2017</b> PLOS Comput Biol</span>
    <span class="chip">Tutorial · <b>CellBasedComparison2017</b></span>
    <span class="chip">Models reproduced · <b>4 / 5</b></span>
    <span class="chip">Reference · <b>authors' own C++ code</b></span>
  </div>
  <div class="verdict">
    <h2>Verdict — {esc(ex.get('verdict_status','').upper())}</h2>
    <p>{esc(ex.get('verdict','').strip())}</p>
  </div>
</header>

<section>
  <h2 class="sec">Reproducibility scorecard</h2>
  <p class="sub">Fractional boundary length at t=110 — our PyChaste wrapper vs the authors'
  C++ tutorial (both at 20×20, relax to t=10, label 50%, seed 0). Divergence is the maximum
  absolute difference over the shared 1-hour sampling grid.</p>
  <table class="scorecard">
    <thead><tr><th>Model</th><th class="num">C++ (tutorial)</th><th class="num">PyChaste (ours)</th>
      <th class="num">max │diff│</th><th>Verdict</th><th>Note</th></tr></thead>
    <tbody>{''.join(sc)}</tbody>
  </table>
</section>

<section>
  <h2 class="sec">Fractional length over time</h2>
  <p class="sub">Sorting trajectories, normalized to the value at labelling (t=10) as in the
  paper's Fig 3. Solid = C++ tutorial, dashed = PyChaste reproduction. Lower = more sorted.</p>
  <div id="overlay"></div>
  <div class="legend">
    <span><i style="border-color:var(--cxx)"></i>C++ tutorial (cbc-01)</span>
    <span><i style="border-color:var(--pyc);border-top-style:dashed"></i>PyChaste (cbc-04)</span>
  </div>
  <figure style="margin-top:22px">
    <img src="{figrel}" alt="Fractional length overlay, C++ vs PyChaste, five model classes">
    <figcaption>Static overlay across all five model classes (CA shown for the C++ tutorial
    only — it is unsupported in PyChaste).</figcaption>
  </figure>
</section>

<section>
  <h2 class="sec">Studies</h2>
  <p class="sub">The investigation runs as four studies: build the C++ reference, extend the
  wrapper, test the one non-mainline substitution adversarially, then reproduce and diff.</p>
  <div class="cards">{''.join(cards)}</div>
</section>

<section>
  <h2 class="sec">How the reproduction works</h2>
  <ul class="tight">
    <li><b>Same engine, not a re-implementation.</b> pbg-chaste drives the real Chaste C++
    library through the official <code>chaste/pychaste</code> image. CP/OS/VT/VM use the
    identical population, force and update-rule classes the tutorial uses.</li>
    <li><b>The measure is Chaste's own.</b> Fractional boundary length comes from Chaste's
    <code>HeterotypicBoundaryLengthWriter</code>, emitted identically by both sides.</li>
    <li><b>One documented substitution.</b> The tutorial's custom <code>RandomMotionForce</code>
    cannot be bound from Python, so OS/VM use mainline <code>DiffusionForce</code>, calibrated to
    the same diffusion constant and verified against free-diffusion MSD (study cbc-03).</li>
    <li><b>The ground truth is regenerated, not read off the page.</b> We built the authors'
    project against <code>chaste/release</code> and ran it to t=100; the comparison is our
    PyChaste output vs that C++ output.</li>
  </ul>
</section>

<section>
  <h2 class="sec">Honest limitations</h2>
  <ul class="tight">
    <li><b>CA is out of reach.</b> The cellular automaton's
    <code>DifferentialAdhesionCaSwitchingUpdateRule</code> is custom to the tutorial repo and
    PyChaste exposes no constructible base to subclass. Reported, not hidden — the C++ baseline
    still includes CA for completeness.</li>
    <li><b>VT runs without random motion.</b> <code>DiffusionForce</code> divides by node radius,
    which the Voronoi population's per-step remesh discards; it still reproduces the tutorial's
    stalled VT within 0.07, because sorting here is adhesion-driven and the noise is second-order.</li>
    <li><b>Single seed.</b> Both sides are seed 0. Point divergences are small (VM 0.012, CP/VT
    ~0.07, OS 0.15) but a 10-seed spread would turn "within run-to-run noise" into a quantitative claim.</li>
  </ul>
</section>

<footer>
  Generated from <code>workspace/investigations/cellbased-comparison-2017/</code> ·
  regenerate with <code>python workspace/investigations/cellbased-comparison-2017/build_report.py</code> ·
  a read-only view of the investigation state; the source of truth is the study YAMLs and the
  committed <code>.dat</code> baselines.
</footer>
</div>
<script>
const TRAJ = {json.dumps(traj)};
function tt(){{const r=document.documentElement;
  const cur=r.getAttribute('data-theme')|| (matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light');
  r.setAttribute('data-theme', cur==='dark'?'light':'dark'); draw();}}
function cssv(n){{return getComputedStyle(document.documentElement).getPropertyValue(n).trim();}}
function draw(){{
  const models=[["cp","CP"],["os","OS"],["vt","VT"],["vm","VM"],["ca","CA"]];
  const cxx=cssv('--cxx'), pyc=cssv('--pyc'), fg=cssv('--fg'), mut=cssv('--mut'), line=cssv('--line');
  const traces=[]; const ann=[];
  const cols=models.length;
  models.forEach((m,i)=>{{
    const key=m[0], d=TRAJ[key]||{{}};
    const xax = i===0?'x':'x'+(i+1); const yax=i===0?'y':'y'+(i+1);
    if(d.cxx) traces.push({{x:d.cxx.x,y:d.cxx.y,xaxis:xax,yaxis:yax,mode:'lines',
      line:{{color:cxx,width:2}},name:'C++',showlegend:false,hovertemplate:m[1]+' C++ t=%{{x:.0f}} %{{y:.2f}}<extra></extra>'}});
    if(d.pyc) traces.push({{x:d.pyc.x,y:d.pyc.y,xaxis:xax,yaxis:yax,mode:'lines',
      line:{{color:pyc,width:2,dash:'dash'}},name:'PyChaste',showlegend:false,hovertemplate:m[1]+' PyChaste t=%{{x:.0f}} %{{y:.2f}}<extra></extra>'}});
    ann.push({{text:m[1],x:0.5,xref:'x'+(i===0?'':i+1)+' domain',y:1.06,yref:'paper',
      showarrow:false,font:{{color:fg,size:13}}}});
  }});
  const layout={{grid:{{rows:1,columns:cols,pattern:'independent'}},
    margin:{{l:44,r:10,t:24,b:36}},paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',
    font:{{color:mut,size:11}},annotations:ann,height:340,
    yaxis:{{range:[0,1.12],gridcolor:line,title:{{text:'frac. (norm)',font:{{size:11}}}},zeroline:false}}}};
  for(let i=2;i<=cols;i++){{layout['yaxis'+i]={{range:[0,1.12],gridcolor:line,zeroline:false,matches:'y',showticklabels:false}};}}
  for(let i=1;i<=cols;i++){{const k='xaxis'+(i===1?'':i);layout[k]={{gridcolor:line,zeroline:false,dtick:50}};}}
  Plotly.react('overlay',traces,layout,{{displayModeBar:false,responsive:true}});
}}
draw();
matchMedia('(prefers-color-scheme:dark)').addEventListener('change',draw);
</script>
</body></html>"""
    out = os.path.join(HERE, "report.html")
    with open(out, "w") as f:
        f.write(doc)
    print("wrote", out, "(%d bytes)" % len(doc))


if __name__ == "__main__":
    render()
