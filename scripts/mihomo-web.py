#!/usr/bin/env python3
"""Mihomo Web 面板：状态/节点/延迟/控制开关 (仅 127.0.0.1)"""
import json
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

API = "http://127.0.0.1:9090"
TEST_URL = "https://www.gstatic.com/generate_204"
MODE_SEQ = ["rule", "global", "direct"]
PORT = 8080

HTML = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>Mihomo 代理面板</title>
<style>
:root{--bg:#0f1115;--fg:#d8dee9;--muted:#7b8494;--card:#171a21;--ok:#4caf50;--warn:#ffb300;--bad:#e53935;--cy:#26c6da;}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 "DejaVu Sans Mono",monospace}
header{display:flex;align-items:center;gap:12px;padding:10px 16px;background:#0b0d11;border-bottom:1px solid #222}
h1{font-size:16px;margin:0}.pill{padding:2px 10px;border-radius:10px;font-size:12px}
.pill.ok{background:#173a24;color:var(--ok)}.pill.bad{background:#3a1a1a;color:var(--bad)}.pill.warn{background:#3a3017;color:var(--warn)}
main{display:grid;grid-template-columns:1fr 1fr;gap:14px;padding:14px}
.card{background:var(--card);border:1px solid #23272f;border-radius:8px;padding:12px}
.card h2{margin:0 0 8px;font-size:13px;color:var(--cy)}
.big{font-size:22px;font-weight:bold}.d1{color:var(--ok)}.d2{color:var(--warn)}.d3{color:var(--bad)}
.mono{color:var(--cy)}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:3px 6px;border-bottom:1px solid #23272f}
th{color:var(--muted);font-weight:normal}
button{background:#23272f;color:var(--fg);border:1px solid #333;border-radius:6px;padding:7px 12px;cursor:pointer;font-size:13px}
button:hover{background:#2c313c}button:disabled{opacity:.5;cursor:not-allowed}
button.danger{border-color:#7a2a2a;color:var(--bad)}button.cy{border-color:#1e6a75;color:var(--cy)}
.controls{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}
.log{margin-top:10px;background:#0b0d11;border:1px solid #23272f;border-radius:6px;padding:8px;height:62px;overflow:auto;font-size:12px;color:var(--muted);white-space:pre-wrap}
.full{grid-column:1/-1}.curline{color:var(--muted)}
.banner{grid-column:1/-1;padding:13px 16px;font-size:17px;font-weight:bold;border-radius:8px;display:flex;align-items:center;gap:10px}
.banner.ok{background:#173a24;color:#7ee787;border:1px solid #2c6640}
.banner.off{background:#3a1a1a;color:#ff6b6b;border:1px solid #7a2a2a}
.banner.warn{background:#3a3017;color:#ffd675;border:1px solid #7a622a}
.banner .dot{width:12px;height:12px;border-radius:50%;background:currentColor;box-shadow:0 0 8px currentColor;flex:none}
.fail{color:var(--bad)}
@media(max-width:900px){main{grid-template-columns:1fr}}
</style>
</head>
<body>
<header>
<h1>🛰 Mihomo 代理面板</h1>
<span class="pill" id="svc">…</span>
<span class="pill" id="boot">…</span>
<span class="pill" id="mode">…</span>
<span id="clock"></span>
</header>
<main>
<div class="banner ok" id="health">检测中…</div>
<div class="card">
<h2>当前节点</h2>
<div id="cur" class="big" style="color:var(--bad)">—</div>
<div class="curline" id="curinfo"></div>
<div class="curline" id="chain"></div>
<div class="controls">
<button id="b_stop" class="danger">■ 停止代理(全直连)</button>
<button id="b_start" class="cy">▶ 启动代理</button>
<button id="b_disable">禁用开机自启</button>
<button id="b_enable">启用开机自启</button>
<button id="b_mode">切换模式</button>
<button id="b_update">立即更新订阅</button>
</div>
<div class="log" id="log"></div>
</div>
<div class="card full" style="grid-column:1/2">
<h2>自动优选 候选节点 (共 <span id="cn">0</span>, 自上而下优先)</h2>
<table id="cands"><tbody></tbody></table>
</div>
<div class="card full" style="grid-column:2/2">
<h2>策略组速览</h2>
<table id="groups"><tbody></tbody></table>
</div>
</main>
<script>
const q=(id)=>document.getElementById(id);
let busy=false;
function delayColor(d){ if(d===null||d===undefined) return 'd3'; return d<300?'d1':d<800?'d2':'d3'; }
function esc(s){ return String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
async function fetchJSON(url,opt){ const r=await fetch(url,opt); if(!r.ok) throw new Error(r.status); return r.json(); }
function log(m){ const el=q('log'); const t='['+new Date().toLocaleTimeString()+'] '+m+String.fromCharCode(10); el.textContent+=t; el.scrollTop=el.scrollHeight; }
async function refresh(){
  try{
    const s=await fetchJSON('/api/status');
    q('svc').textContent='服务:'+s.service; q('svc').className='pill '+(s.service==='active'?'ok':'bad');
    q('boot').textContent='自启:'+(s.enabled?'ON':'OFF'); q('boot').className='pill '+(s.enabled?'ok':'warn');
    q('mode').textContent='模式:'+s.mode;
    q('clock').textContent=new Date().toLocaleTimeString();
    const cur=s.current, cd=s.curDelay;
    const h=s.health||{level:'warn',label:'检测中…'};
    q('health').className='banner '+h.level;
    q('health').innerHTML='<span class="dot"></span>'+esc(h.label);
    q('cur').textContent=cur||'—'; q('cur').className='big '+delayColor(cd);
    q('cur').textContent+='  '+((cd!==null&&cd!==undefined)?cd+'ms':'FAIL');
    q('curinfo').textContent='重启次数: '+s.restarts+'  ·  自动优选当前: '+(s.chain&&s.chain.auto?s.chain.auto:'—');
    q('chain').textContent=s.chain?('🐟'+s.chain.fish+' → 🔰'+s.chain.sel+' → 🚀'+s.chain.auto):'';
    q('cn').textContent=s.cands.length;
    let th=''; let mark='';
    for(const c of s.cands){
      mark=(c.name===cur)?' ◆':'';
      const dl=(c.delay===null||c.delay===undefined)?'—':c.delay+'ms';
      th+='<tr><td class="mono">'+esc(c.name+mark)+'</td><td class="'+delayColor(c.delay)+'">'+dl+'</td></tr>';
    }
    q('cands').querySelector('tbody').innerHTML=th;
    let tg='';
    for(const g of s.groups){
      const dl=(g.delay===null||g.delay===undefined)?'—':g.delay+'ms';
      tg+='<tr><td class="mono">'+esc(g.name)+'</td><td>'+esc(g.now)+'</td><td class="'+delayColor(g.delay)+'">'+dl+'</td></tr>';
    }
    q('groups').querySelector('tbody').innerHTML=tg;
  }catch(e){ q('svc').textContent='!! 面板接口异常'; q('svc').className='pill bad'; }
}
async function act(a){ if(busy)return; busy=true; log('执行: '+a); try{ const r=await fetchJSON('/api/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:a})}); log(r.msg||r.error||'ok'); }catch(e){ log('失败: '+e); } busy=false; setTimeout(refresh,400); }
document.addEventListener('DOMContentLoaded',()=>{
  q('b_stop').onclick=()=>act('stop'); q('b_start').onclick=()=>act('start');
  q('b_disable').onclick=()=>act('disable'); q('b_enable').onclick=()=>act('enable');
  q('b_mode').onclick=()=>act('mode'); q('b_update').onclick=()=>act('update');
  refresh(); setInterval(refresh,3000);
});
</script>
</body>
</html>
"""


def hamo(path):
    try:
        with urllib.request.urlopen(API + path, timeout=6) as r:
            return json.load(r)
    except Exception:
        return {}

_probe = {"cur": None, "t": 0.0, "delay": None}


def probe_node(name):
    global _probe
    now = time.time()
    if _probe["cur"] == name and now - _probe["t"] < 10:
        return _probe["delay"]
    try:
        with urllib.request.urlopen(API + "/proxies/" + urllib.parse.quote(name) +
                                    "/delay?timeout=5000&url=" + urllib.parse.quote(TEST_URL, safe=""),
                                    timeout=6) as r:
            d = json.load(r).get("delay")
            d = d if isinstance(d, int) and d > 0 else None
    except Exception:
        d = None
    _probe["cur"], _probe["t"], _probe["delay"] = name, now, d
    return d


def run(cmd, sudo=False):
    c = ["sudo"] + cmd if sudo else cmd
    try:
        r = subprocess.run(c, capture_output=True, text=True, timeout=30)
        return (r.returncode, r.stdout + r.stderr)
    except Exception as e:
        return (1, str(e))


def status():
    cfg = hamo("/configs")
    proxies = hamo("/proxies").get("proxies", {})
    svc = run(["systemctl", "show", "mihomo", "-p", "ActiveState",
               "-p", "NRestarts", "-p", "UnitFileState"])[1]
    d = {}
    for ln in svc.splitlines():
        if "=" in ln:
            k, vv = ln.split("=", 1)
            d[k] = vv
    auto = proxies.get("🚀 自动优选") or proxies.get("🔰 选择节点") or {}
    cur = auto.get("now")
    cands = []
    for n in (auto.get("all") or [])[:40]:
        hist = (proxies.get(n) or {}).get("history") or []
        cands.append({"name": n, "delay": hist[-1].get("delay") if hist else None})
    groups = []
    for k, v in proxies.items():
        if isinstance(v, dict) and v.get("type") in ("Selector", "URLTest", "Fallback"):
            hist = v.get("history") or []
            groups.append({"name": k, "now": v.get("now", ""),
                           "delay": hist[-1].get("delay") if hist else None})
    chain = {}
    if proxies:
        chain = {"fish": proxies.get("🐟 漏网之鱼", {}).get("now"),
                 "sel": proxies.get("🔰 选择节点", {}).get("now"),
                 "auto": proxies.get("🚀 自动优选", {}).get("now")}
    curDelay = None
    if cur:
        hist = (proxies.get(cur) or {}).get("history") or []
        curDelay = hist[-1].get("delay") if hist else None
    svc_active = d.get("ActiveState") == "active"
    if not svc_active:
        health = {"level": "off", "label": "已断开连接 · 当前全直连"}
    elif not proxies or cfg.get("error"):
        health = {"level": "warn", "label": "代理运行中 · 面板接口异常，请查看日志"}
    else:
        pd = probe_node(cur) if cur else None
        if pd is None:
            health = {"level": "warn", "label": "代理连接中 · 节点链路异常，正在自动切换节点"}
        else:
            health = {"level": "ok", "label": f"代理连接中 · 通过 {cur} · {pd}ms"}
    return {
        "service": d.get("ActiveState", "?"),
        "restarts": d.get("NRestarts", "?"),
        "enabled": d.get("UnitFileState") == "enabled",
        "mode": cfg.get("mode", "?"),
        "current": cur, "curDelay": curDelay,
        "chain": chain, "cands": cands, "groups": groups,
        "health": health,
    }


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def sendj(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            body = HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/status":
            self.sendj(status())
        else:
            self.sendj({"error": "not found"}, 404)

    def do_POST(self):
        if self.path != "/api/control":
            self.sendj({"error": "not found"}, 404)
            return
        try:
            a = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0)).get("action")
        except Exception:
            self.sendj({"error": "bad request"}, 400)
            return
        if a == "stop":
            run(["systemctl", "stop", "mihomo"])
            self.sendj({"msg": "已停止代理, 当前全直连"})
        elif a == "start":
            run(["systemctl", "start", "mihomo"])
            self.sendj({"msg": "已启动代理"})
        elif a == "disable":
            run(["systemctl", "disable", "mihomo"])
            self.sendj({"msg": "已禁用开机自启(服务已停)"})
            run(["systemctl", "stop", "mihomo"])
        elif a == "enable":
            run(["systemctl", "enable", "mihomo"])
            self.sendj({"msg": "已启用开机自启(服务已启动)"})
            run(["systemctl", "start", "mihomo"])
        elif a == "mode":
            cfg = hamo("/configs")
            m = cfg.get("mode", "rule")
            nxt = MODE_SEQ[(MODE_SEQ.index(m) + 1) % len(MODE_SEQ)] if m in MODE_SEQ else "rule"
            try:
                req = urllib.request.Request(API + "/configs", data=json.dumps({"mode": nxt}).encode(),
                                             headers={"Content-Type": "application/json"}, method="PATCH")
                urllib.request.urlopen(req, timeout=5)
                self.sendj({"msg": f"模式切换为 {nxt}"})
            except Exception as e:
                self.sendj({"error": str(e)}, 500)
        elif a == "update":
            rc, out = run(["/usr/local/bin/update-mihomo-sub.sh"])
            self.sendj({"msg": "订阅更新完成" if rc == 0 else "订阅更新失败", "detail": out[-300:]})
        else:
            self.sendj({"error": "unknown action"}, 400)


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    print(f"Mihomo Web 面板: http://127.0.0.1:{PORT}")
    srv.serve_forever()