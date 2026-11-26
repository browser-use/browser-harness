#!/usr/bin/env python3
"""Live check: many agents on one daemon. Needs a running daemon (local or cloud).

Each agent owns one tab and runs separate CLI invocations (one per turn, like a
real LLM agent). A turn fails when it reads, screenshots or clicks another
agent's tab, errors or times out. Without --agent-env every agent is the same
owner (one shared current tab); with --agent-env BH_OWNER each has its own tabs.

  ./browser-harness <<'PY'
  start_remote_daemon("bench")
  PY
  python tests/integration/multi_agent_bench.py --cmd ./browser-harness --name bench \
      --agents 5 --steps 10 --runs 3 --out before.jsonl
  python tests/integration/multi_agent_bench.py --cmd ./browser-harness --name bench \
      --agents 5 --steps 10 --runs 3 --agent-env BH_OWNER --out after.jsonl

Needs Pillow (a harness dependency) for the screenshot colour check.
"""
import argparse, json, os, random, re, subprocess, sys, tempfile, threading, time, uuid
from pathlib import Path

COLORS = ["#ff0000", "#00ff00", "#0000ff", "#ffff00", "#ff00ff", "#00ffff", "#ff8800", "#8800ff"]

def page_url(i):
    c = COLORS[i % len(COLORS)]
    html = (f"<title>agent-{i}</title><body style='margin:0;background:{c}'>"
            f"<h1 id=who style='position:absolute;left:300px;top:300px;font-size:12px'>agent-{i}</h1>"
            f"<script>window.__n=0;document.body.onclick=()=>{{window.__n++}}</script></body>")
    return "data:text/html," + html.replace("#", "%23").replace(" ", "%20").replace("'", "%27")

def run_cli(cmd, name, script, env_extra, timeout=90):
    env = {**os.environ, "BU_NAME": name, **env_extra}
    t0 = time.monotonic()
    try:
        p = subprocess.run([cmd], input=script, text=True, capture_output=True, timeout=timeout, env=env)
        return {"rc": p.returncode, "out": p.stdout, "err": p.stderr[-800:], "dt": round(time.monotonic() - t0, 2)}
    except subprocess.TimeoutExpired as e:
        return {"rc": -1, "out": (e.stdout or ""), "err": "TIMEOUT " + (e.stderr or "")[-300:], "dt": round(time.monotonic() - t0, 2)}

def last_json(out):
    for line in reversed(out.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try: return json.loads(line)
            except Exception: pass
    return None

def _clean_title(t):
    # harness marks its tab titles: "\U0001F434 title" (0.1.13) or "\U0001F434<owner> title" (0.1.14)
    return re.sub(r"^\U0001F434\S*\s*", "", str(t or "")).strip()

def classify(res, obs, me, expect):
    if res["rc"] == -1: return "timeout"
    low = (res["err"] + res["out"]).lower()
    if any(k in low for k in ("not_attached", "session with given id not found", "cdp_disconnected", "no session", "daemon is shutting down")):
        return "lost_attach"
    if res["rc"] != 0 or obs is None: return "error"
    if _clean_title(obs.get("title")) != me: return "wrong_tab"
    if expect == "shot" and not obs.get("shot_ok"): return "wrong_screenshot"
    if expect == "click" and not obs.get("click_ok"): return "click_miss"
    return "ok"

def center_color(path):
    from PIL import Image
    im = Image.open(path).convert("RGB")
    w, h = im.size
    return im.getpixel((w // 2, h // 4))

def worker(i, args, run_id, results, tids, lock):
    me = f"agent-{i}"
    url = page_url(i)
    env_extra = {args.agent_env: f"{run_id}-{me}"} if args.agent_env else {}
    shot = str(Path(tempfile.gettempdir()) / f"bench-{run_id}-{i}.png")
    want = tuple(int(COLORS[i % len(COLORS)][k:k+2], 16) for k in (1, 3, 5))
    def rec(step, kind, res, obs, cls):
        with lock:
            results.append({"run": run_id, "agent": me, "step": step, "kind": kind, "class": cls,
                            "dt": res["dt"], "observed": (obs or {}).get("title"), "err": res["err"][-200:] if cls != "ok" else ""})
    # step 0: open my tab
    s = f"tid=new_tab({url!r}); wait_for_load(5); import json; print(json.dumps({{'tid':tid,'title':js('document.title'),'url':current_tab()['url']}}))"
    res = run_cli(args.cmd, args.name, s, env_extra)
    obs = last_json(res["out"])
    cls = classify(res, obs, me, "open")
    rec(0, "open", res, obs, cls)
    tid = (obs or {}).get("tid")
    with lock: tids[me] = tid
    if not tid: return
    n = 0
    for step in range(1, args.steps + 1):
        time.sleep(random.uniform(0, 0.3))
        kind = random.choice(["info", "click", "shot", "js"])
        pre = f"switch_tab({tid!r})\n" if args.mode == "reswitch" else ""
        if kind == "info":
            s = pre + "import json; p=page_info(); print(json.dumps({'title':p.get('title'),'url':p.get('url')}))"
        elif kind == "js":
            s = pre + "import json; print(json.dumps({'title':js('document.title'),'who':js(\"document.getElementById('who')&&document.getElementById('who').textContent\")}))"
        elif kind == "click":
            s = pre + f"import json; before=js('window.__n'); click_at_xy(100,100); after=js('window.__n'); print(json.dumps({{'title':js('document.title'),'click_ok': (after==before+1) if isinstance(before,int) else False,'before':before,'after':after}}))"
        else:
            s = pre + f"import json; p=capture_screenshot({shot!r}); print(json.dumps({{'title':js('document.title'),'path':p}}))"
        res = run_cli(args.cmd, args.name, s, env_extra)
        obs = last_json(res["out"])
        if kind == "shot" and obs is not None and os.path.exists(shot):
            try:
                c = center_color(shot)
                obs["shot_ok"] = all(abs(a - b) < 40 for a, b in zip(c, want))
                obs["color"] = c
            except Exception as e:
                obs["shot_ok"] = False; obs["color"] = str(e)
        cls = classify(res, obs, me, kind)
        rec(step, kind, res, obs, cls)
    run_cli(args.cmd, args.name, f"close_tab({tid!r})", env_extra, timeout=30)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cmd", default="browser-harness")
    ap.add_argument("--name", required=True)
    ap.add_argument("--agents", type=int, default=4)
    ap.add_argument("--steps", type=int, default=10)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--mode", choices=["naive", "reswitch"], default="naive")
    ap.add_argument("--agent-env", default="")
    ap.add_argument("--label", default="")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    all_results = []
    for r in range(args.runs):
        run_id = f"{args.label or 'run'}-{r}-{uuid.uuid4().hex[:4]}"
        results, tids, lock = [], {}, threading.Lock()
        ths = [threading.Thread(target=worker, args=(i, args, run_id, results, tids, lock)) for i in range(args.agents)]
        [t.start() for t in ths]; [t.join() for t in ths]
        dup = len(tids) - len(set(v for v in tids.values() if v))
        for x in results: x["tab_collisions"] = dup
        all_results += results
        tot = len(results); bad = sum(1 for x in results if x["class"] != "ok")
        print(f"run {run_id}: {bad}/{tot} failed, tab_collisions={dup}", flush=True)
    with open(args.out, "a") as f:
        for x in all_results: f.write(json.dumps(x) + "\n")
    from collections import Counter
    c = Counter(x["class"] for x in all_results)
    tot = len(all_results)
    print(json.dumps({"label": args.label, "cmd": args.cmd, "mode": args.mode, "agents": args.agents, "steps": args.steps,
                      "runs": args.runs, "agent_env": args.agent_env, "total": tot,
                      "failed": tot - c["ok"], "fail_rate": round((tot - c["ok"]) / max(tot, 1), 3), "by_class": dict(c)}))

if __name__ == "__main__":
    main()
