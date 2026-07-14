"""Generate a self-contained HTML report for pbg-chaste.

Runs several *sub-cellular × multi-cellular* combinations through the REAL
Chaste engine (via ChasteSession / the chaste/pychaste container), collects
per-step trajectories and final cell layouts, and renders an interactive report
with Plotly time-series, spatial cell maps, a bigraph diagram, and a PBG
document tree.

Usage:
    python demo/demo_report.py            # runs combos, writes demo/report.html
    python demo/demo_report.py --quick    # fewer steps
"""
from __future__ import annotations

import html
import json
import os
import sys
import time
import webbrowser
from pathlib import Path

from pbg_chaste import runtime
from pbg_chaste.composites import build_document

HERE = Path(__file__).resolve().parent
OUT = HERE / "report.html"

# Each panel: a distinct subcellular × multicellular combination.
CONFIGS = [
    {
        "id": "mesh_uniform",
        "title": "Mesh · Uniform cycle",
        "subtitle": "Voronoi/spring tissue, simple proliferation",
        "population": "mesh", "cell_cycle": "uniform",
        "width": 4, "height": 4, "steps": 6, "interval": 2.0,
        "accent": "#2563eb",
        "blurb": "A mesh-based (overlapping-Voronoi + linear spring) population "
                 "with the simplest sub-cellular clock: a uniformly-drawn total "
                 "cycle time. Cells proliferate and the disc spreads.",
    },
    {
        "id": "node_stochastic",
        "title": "Node · Stochastic cycle",
        "subtitle": "Overlapping spheres, exponential G1",
        "population": "node", "cell_cycle": "stochastic",
        "width": 4, "height": 4, "steps": 6, "interval": 2.0,
        "accent": "#0d9488",
        "blurb": "A node-based (overlapping spheres, cut-off spring) population "
                 "with an exponentially-distributed G1 phase — a genuinely "
                 "stochastic sub-cellular timer driving heterogeneous division.",
    },
    {
        "id": "vertex_tyson_novak",
        "title": "Vertex · Tyson–Novak ODE",
        "subtitle": "Confluent epithelium, biochemical oscillator",
        "population": "vertex", "cell_cycle": "tyson_novak",
        "width": 3, "height": 3, "steps": 6, "interval": 1.0,
        "accent": "#7c3aed",
        "blurb": "A vertex-based (Nagai–Honda polygonal) confluent epithelium "
                 "whose sub-cellular model is the Tyson–Novak ODE system — a real "
                 "biochemical cell-cycle oscillator solved per cell, gating "
                 "division on the underlying protein dynamics.",
    },
    {
        "id": "mesh_delta_notch",
        "title": "Mesh · Delta–Notch SRN",
        "subtitle": "Lateral-inhibition patterning",
        "population": "mesh", "cell_cycle": "delta_notch",
        "width": 5, "height": 5, "steps": 6, "interval": 1.0,
        "accent": "#dc2626",
        "blurb": "Each cell carries a Delta–Notch sub-cellular reaction network "
                 "coupled to its neighbours (Collier lateral inhibition). Watch "
                 "the mean Delta/Notch signals evolve as the pattern forms.",
    },
]


def run_config(cfg, quick=False):
    steps = 3 if quick else cfg["steps"]
    result = {"cfg": cfg, "ok": False, "series": [], "frames": [],
              "error": None, "elapsed": 0.0}
    t0 = time.time()
    try:
        s = runtime.ChasteSession(
            {"population": cfg["population"], "cell_cycle": cfg["cell_cycle"],
             "width": cfg["width"], "height": cfg["height"], "seed": 0,
             "sampling_multiple": 12},
            step_timeout=180.0, start_timeout=420.0,
        )
        init = s.start()
        result["series"].append({"time": 0.0, "num_cells": init["num_cells"],
                                 "mean_delta": init.get("mean_delta", 0.0),
                                 "mean_notch": init.get("mean_notch", 0.0)})
        for _ in range(steps):
            st = s.step(interval=cfg["interval"], stiffness=0.0)
            result["series"].append({
                "time": st["time"], "num_cells": st["num_cells"],
                "mean_delta": st.get("mean_delta", 0.0),
                "mean_notch": st.get("mean_notch", 0.0),
            })
            pos = st.get("positions", [])
            result["frames"].append({
                "time": st["time"],
                "x": [p[0] for p in pos],
                "y": [p[1] for p in pos],
                "delta": st.get("per_cell_delta", []),
            })
        s.close()
        result["ok"] = True
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
    result["elapsed"] = time.time() - t0
    return result


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------
def _bigraph_svg(cfg, first=False):
    """Interactive bigraph fragment for one composite (bigraph-viz2).

    The FIRST fragment on the page must inline the shared CSS/JS bundle
    (dedupe=False); later fragments drop their copy (dedupe=True). Getting
    this backwards yields empty shells that render nothing.
    """
    try:
        from bigraph_viz2 import emit_html  # type: ignore
        doc = build_document(cfg["population"], cfg["cell_cycle"],
                             width=cfg["width"], height=cfg["height"])
        return emit_html(doc, id=f"bg_{cfg['id']}", height="360px",
                         inspector=True, dedupe=not first)
    except Exception:
        return _bigraph_fallback(cfg)


def animation_html(pid, frames, accent, is_dn):
    """A Plotly play/pause animation of the cell population over time."""
    frames = [f for f in frames if f["x"]]
    if not frames:
        return '<div class="muted">no spatial frames captured</div>'
    all_x = [v for f in frames for v in f["x"]]
    all_y = [v for f in frames for v in f["y"]]
    pad = 1.0
    xr = [min(all_x) - pad, max(all_x) + pad]
    yr = [min(all_y) - pad, max(all_y) + pad]

    def marker(f):
        if is_dn:
            return dict(size=18, color=f["delta"], colorscale="YlOrRd",
                        cmin=0.0, cmax=1.0, showscale=True,
                        colorbar=dict(title="Delta", thickness=12),
                        line=dict(color="#334155", width=1))
        return dict(size=16, color=accent, opacity=0.85,
                    line=dict(color="white", width=1.5))

    def trace(f):
        return dict(x=f["x"], y=f["y"], mode="markers", type="scatter",
                    marker=marker(f))

    pframes = [dict(name=f"{i}", data=[trace(f)]) for i, f in enumerate(frames)]
    steps = [dict(label=f'{f["time"]:.0f}', method="animate",
                  args=[[f"{i}"], dict(mode="immediate",
                                       frame=dict(duration=0, redraw=True))])
             for i, f in enumerate(frames)]
    layout = dict(
        margin=dict(t=24, r=12, b=44, l=44), height=360,
        xaxis=dict(range=xr, scaleanchor="y", scaleratio=1, title="x"),
        yaxis=dict(range=yr, title="y"),
        paper_bgcolor="white", plot_bgcolor="#fafafa",
        updatemenus=[dict(type="buttons", showactive=False, x=0.02, y=1.12,
                          xanchor="left", direction="left",
                          buttons=[
            dict(label="▶ play", method="animate",
                 args=[None, dict(frame=dict(duration=650, redraw=True),
                                  transition=dict(duration=180),
                                  fromcurrent=True)]),
            dict(label="❚❚ pause", method="animate",
                 args=[[None], dict(mode="immediate",
                                    frame=dict(duration=0, redraw=False))]),
        ])],
        sliders=[dict(active=0, x=0.12, len=0.85, y=-0.02,
                      currentvalue=dict(prefix="t = ", suffix=" h",
                                        font=dict(size=13)),
                      steps=steps)],
    )
    return f"""
    <div id="an_{pid}" class="chart"></div>
    <script>
    (function(){{
      var frames = {json.dumps(pframes)};
      Plotly.newPlot('an_{pid}', frames[0].data, {json.dumps(layout)},
        {{displayModeBar:false, responsive:true}})
        .then(function(){{ Plotly.addFrames('an_{pid}', frames); }});
    }})();
    </script>"""


def _bigraph_fallback(cfg):
    return f"""
    <div class="bg-fallback">
      <div class="bg-node proc" style="border-color:{cfg['accent']}">
        ChasteSimulationProcess<br><span>{cfg['population']} × {cfg['cell_cycle']}</span>
      </div>
      <div class="bg-arrows">
        <div class="bg-in">spring_stiffness →</div>
        <div class="bg-out">→ num_cells, positions,<br>phase_counts, mean_delta/notch</div>
      </div>
      <div class="bg-node store">stores</div>
      <div class="bg-node emit">RAMEmitter</div>
    </div>"""


def json_tree(obj, depth=0):
    """Collapsible coloured JSON tree."""
    pad = "  " * depth
    if isinstance(obj, dict):
        if not obj:
            return '<span class="j-brace">{}</span>'
        rows = []
        for k, v in obj.items():
            rows.append(f'{pad}  <span class="j-key">"{html.escape(str(k))}"</span>: '
                        + json_tree(v, depth + 1))
        inner = ",\n".join(rows)
        collapse = ' data-collapsed="1"' if depth >= 2 else ""
        return (f'<span class="j-brace j-toggle"{collapse}>{{</span>'
                f'<span class="j-body">\n{inner}\n{pad}</span>'
                f'<span class="j-brace">}}</span>')
    if isinstance(obj, list):
        if len(obj) <= 6 and all(isinstance(x, (int, float, str)) for x in obj):
            return ('<span class="j-brace">[</span>'
                    + ", ".join(json_tree(x, depth + 1) for x in obj)
                    + '<span class="j-brace">]</span>')
        rows = [f'{pad}  ' + json_tree(x, depth + 1) for x in obj]
        return (f'<span class="j-brace j-toggle" data-collapsed="1">[</span>'
                f'<span class="j-body">\n' + ",\n".join(rows) + f'\n{pad}</span>'
                f'<span class="j-brace">]</span>')
    if isinstance(obj, str):
        return f'<span class="j-str">"{html.escape(obj)}"</span>'
    if isinstance(obj, bool):
        return f'<span class="j-bool">{str(obj).lower()}</span>'
    if obj is None:
        return '<span class="j-null">null</span>'
    return f'<span class="j-num">{obj}</span>'


def render(results, meta):
    panels = "\n".join(render_panel(r, i) for i, r in enumerate(results))
    nav = "\n".join(
        f'<a href="#{r["cfg"]["id"]}">{html.escape(r["cfg"]["title"])}</a>'
        for r in results
    )
    n_ok = sum(1 for r in results if r["ok"])
    total_time = sum(r["elapsed"] for r in results)
    engine = "real Chaste (chaste/pychaste)" if meta["chaste_ready"] else \
        "engine unavailable — Docker/image missing"
    return TEMPLATE.format(
        panels=panels, nav=nav, n_ok=n_ok, n_total=len(results),
        engine=html.escape(engine), total_time=f"{total_time:.0f}",
        generated=meta["generated"],
    )


def render_panel(r, idx=0):
    cfg = r["cfg"]
    pid = cfg["id"]
    accent = cfg["accent"]
    is_dn = cfg["cell_cycle"] == "delta_notch"
    if not r["ok"]:
        body = (f'<div class="err">Run did not complete: '
                f'<code>{html.escape(r["error"] or "?")}</code><br>'
                f'This panel needs the Chaste container '
                f'(<code>docker pull chaste/pychaste</code> + a running daemon).</div>')
        chart = metrics = spatial = ""
    else:
        series = r["series"]
        times = [p["time"] for p in series]
        counts = [p["num_cells"] for p in series]
        n0, n1 = counts[0], counts[-1]
        growth = (n1 / n0) if n0 else 1.0
        metrics = f"""
        <div class="metrics">
          <div class="metric"><div class="mv" style="color:{accent}">{n1}</div><div class="ml">cells (final)</div></div>
          <div class="metric"><div class="mv" style="color:{accent}">{growth:.2f}×</div><div class="ml">growth</div></div>
          <div class="metric"><div class="mv" style="color:{accent}">{times[-1]:.0f}</div><div class="ml">sim time (h)</div></div>
          <div class="metric"><div class="mv" style="color:{accent}">{r['elapsed']:.0f}s</div><div class="ml">wall-clock</div></div>
        </div>"""
        # count trace + (if DN) delta/notch trace
        traces = [dict(x=times, y=counts, mode="lines+markers", name="cell count",
                       line=dict(color=accent, width=3))]
        chart_extra = ""
        if is_dn:
            md = [p["mean_delta"] for p in series]
            mn = [p["mean_notch"] for p in series]
            chart_extra = f"""
            <div id="dn_{pid}" class="chart"></div>
            <script>Plotly.newPlot('dn_{pid}', [
              {{x:{times}, y:{md}, mode:'lines+markers', name:'mean Delta', line:{{color:'#dc2626',width:3}}}},
              {{x:{times}, y:{mn}, mode:'lines+markers', name:'mean Notch', line:{{color:'#2563eb',width:3}}}}
            ], {{margin:{{t:24,r:12,b:36,l:44}}, height:280, legend:{{orientation:'h'}},
                 xaxis:{{title:'time (h)'}}, yaxis:{{title:'SRN signal'}},
                 paper_bgcolor:'white', plot_bgcolor:'#fafafa'}}, {{displayModeBar:false, responsive:true}});
            </script>"""
        chart = f"""
        <div id="ct_{pid}" class="chart"></div>
        <script>Plotly.newPlot('ct_{pid}', {json.dumps(traces)},
          {{margin:{{t:24,r:12,b:36,l:44}}, height:280,
            xaxis:{{title:'time (h)'}}, yaxis:{{title:'number of cells'}},
            paper_bgcolor:'white', plot_bgcolor:'#fafafa'}},
          {{displayModeBar:false, responsive:true}});</script>{chart_extra}"""
        # spatial animation ("video") of the cells over time
        spatial = animation_html(pid, r["frames"], accent, is_dn)

    doc = build_document(cfg["population"], cfg["cell_cycle"],
                        width=cfg["width"], height=cfg["height"])
    bg = _bigraph_svg(cfg, first=(idx == 0))
    tree = json_tree(doc)
    return f"""
    <section id="{pid}" class="panel" style="--accent:{accent}">
      <div class="panel-head">
        <h2>{html.escape(cfg['title'])}</h2>
        <p class="sub">{html.escape(cfg['subtitle'])}</p>
      </div>
      <p class="blurb">{html.escape(cfg['blurb'])}</p>
      {metrics if r['ok'] else ''}
      <div class="grid2">
        <div class="card"><h3>Population dynamics</h3>{chart if r['ok'] else body}</div>
        <div class="card"><h3>Simulation ▶ (cells over time)</h3>{spatial if r['ok'] else '<div class="muted">—</div>'}</div>
      </div>
      <div class="grid2">
        <div class="card"><h3>Bigraph wiring</h3>{bg}</div>
        <div class="card"><h3>PBG document</h3><pre class="jtree">{tree}</pre></div>
      </div>
    </section>"""


TEMPLATE = """<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>pbg-chaste · sub-cellular × multi-cellular</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
:root{{--bg:#f7f8fa;--fg:#1e293b;--mut:#64748b;--card:#fff;--line:#e5e7eb}}
*{{box-sizing:border-box}}
body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
background:var(--bg);color:var(--fg);line-height:1.55}}
header{{padding:48px 24px 28px;max-width:1180px;margin:0 auto}}
h1{{font-size:2.1rem;margin:0 0 6px}}
.lede{{color:var(--mut);font-size:1.05rem;max-width:760px}}
.chips{{margin-top:16px;display:flex;gap:10px;flex-wrap:wrap}}
.chip{{background:#fff;border:1px solid var(--line);border-radius:999px;padding:6px 14px;
font-size:.85rem;color:var(--mut)}}
.chip b{{color:var(--fg)}}
nav{{position:sticky;top:0;z-index:10;background:rgba(247,248,250,.92);backdrop-filter:blur(8px);
border-bottom:1px solid var(--line);padding:10px 24px}}
nav .in{{max-width:1180px;margin:0 auto;display:flex;gap:8px;flex-wrap:wrap}}
nav a{{font-size:.85rem;color:var(--mut);text-decoration:none;padding:5px 12px;border-radius:8px;
border:1px solid transparent}}
nav a:hover{{background:#fff;border-color:var(--line);color:var(--fg)}}
main{{max-width:1180px;margin:0 auto;padding:24px}}
.panel{{background:transparent;margin:0 0 40px;padding:24px 0;border-top:3px solid var(--accent)}}
.panel-head h2{{margin:14px 0 2px;font-size:1.5rem}}
.sub{{color:var(--mut);margin:0 0 6px}}
.blurb{{max-width:820px;color:#334155}}
.metrics{{display:flex;gap:14px;flex-wrap:wrap;margin:14px 0 20px}}
.metric{{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px 20px;min-width:120px}}
.mv{{font-size:1.7rem;font-weight:700}}
.ml{{color:var(--mut);font-size:.82rem}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-bottom:18px}}
@media(max-width:820px){{.grid2{{grid-template-columns:1fr}}}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px}}
.card h3{{margin:0 0 12px;font-size:1rem}}
.chart{{width:100%}}
.muted{{color:var(--mut)}}
.err{{background:#fef2f2;border:1px solid #fecaca;color:#991b1b;border-radius:10px;padding:14px}}
.jtree{{font-family:'SF Mono',Menlo,Consolas,monospace;font-size:.8rem;background:#fbfbfd;
border:1px solid var(--line);border-radius:10px;padding:14px;overflow:auto;max-height:360px}}
.j-key{{color:#7c3aed}} .j-str{{color:#059669}} .j-num{{color:#2563eb}}
.j-bool{{color:#d97706}} .j-null{{color:#94a3b8}} .j-brace{{color:#334155}}
.j-toggle{{cursor:pointer}} .j-toggle:hover{{background:#eef}}
.j-body.collapsed{{display:none}}
.bg-fallback{{display:flex;flex-direction:column;gap:10px;align-items:center;padding:20px}}
.bg-node{{border:2px solid #cbd5e1;border-radius:10px;padding:10px 16px;text-align:center;font-size:.85rem}}
.bg-node.proc{{font-weight:600}} .bg-node span{{color:var(--mut);font-size:.78rem}}
.bg-arrows{{display:flex;gap:24px;color:var(--mut);font-size:.78rem;text-align:center}}
footer{{max-width:1180px;margin:0 auto;padding:24px;color:var(--mut);font-size:.85rem;
border-top:1px solid var(--line)}}
code{{font-family:'SF Mono',Menlo,monospace;font-size:.85em;background:#f1f5f9;padding:1px 5px;border-radius:5px}}
</style></head><body>
<header>
  <h1>Chaste as a process-bigraph composite</h1>
  <p class="lede">One parametrized <code>ChasteSimulationProcess</code> wraps the real
  Chaste engine. Each panel below couples a <b>multi-cellular</b> population method
  (mesh / node / vertex) with a <b>sub-cellular</b> cell-cycle model
  (uniform / stochastic / Tyson–Novak ODE / Delta–Notch SRN) — the same wrapper,
  different combinations.</p>
  <div class="chips">
    <span class="chip">engine: <b>{engine}</b></span>
    <span class="chip"><b>{n_ok}/{n_total}</b> combinations ran</span>
    <span class="chip">total wall-clock: <b>{total_time}s</b></span>
    <span class="chip">generated <b>{generated}</b></span>
  </div>
</header>
<nav><div class="in">{nav}</div></nav>
<main>{panels}</main>
<footer>
  Generated by <code>demo/demo_report.py</code>. Each panel is a genuine Chaste
  <code>OffLatticeSimulation</code> stepped through a resident
  <code>chaste/pychaste</code> container — no reimplementation. Upstream:
  <code>github.com/Chaste/Chaste</code>.
</footer>
<script>
document.querySelectorAll('.j-toggle').forEach(function(t){{
  if(t.dataset.collapsed){{var b=t.nextElementSibling; if(b&&b.classList.contains('j-body'))b.classList.add('collapsed');}}
  t.addEventListener('click',function(){{var b=t.nextElementSibling;
    if(b&&b.classList.contains('j-body'))b.classList.toggle('collapsed');}});
}});
</script>
</body></html>"""


def main():
    quick = "--quick" in sys.argv
    meta = {
        "chaste_ready": runtime.chaste_ready(),
        "generated": time.strftime("%Y-%m-%d %H:%M"),
    }
    if not meta["chaste_ready"]:
        print("WARNING: Chaste container not available — panels will show the "
              "unavailable state. Pull chaste/pychaste + start Docker for real runs.")
    results = []
    for cfg in CONFIGS:
        print(f"running {cfg['id']} ...", flush=True)
        r = run_config(cfg, quick=quick)
        status = "ok" if r["ok"] else f"FAILED ({r['error']})"
        print(f"  {status} in {r['elapsed']:.0f}s", flush=True)
        results.append(r)
    OUT.write_text(render(results, meta))
    print(f"\nwrote {OUT}")
    try:
        webbrowser.open("file://" + str(OUT))
    except Exception:
        pass


if __name__ == "__main__":
    main()
