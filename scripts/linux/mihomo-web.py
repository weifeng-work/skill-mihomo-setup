#!/usr/bin/env python3
"""Mihomo Web 面板 - Linux 平台层。

仅含 Linux/systemd 专属逻辑：systemctl 服务探测与控制、订阅更新脚本。
其余（HTML/API 解析/路由）由 scripts/shared/mihomo_web_common.py 提供。
用法: python3 scripts/linux/mihomo-web.py   (http://127.0.0.1:8080)
"""
import os
import subprocess
import sys
from http.server import ThreadingHTTPServer

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)
sys.path.insert(0, os.path.join(_here, "..", "shared"))
from mihomo_web_common import PORT, make_handler

SVC = "mihomo"


def run(cmd, sudo=False):
    c = ["sudo"] + cmd if sudo else cmd
    try:
        r = subprocess.run(c, capture_output=True, text=True, timeout=30)
        return (r.returncode, r.stdout + r.stderr)
    except Exception as e:
        return (1, str(e))


def svc_status():
    raw = run(["systemctl", "show", SVC, "-p", "ActiveState",
               "-p", "NRestarts", "-p", "UnitFileState"])[1]
    d = {}
    for ln in raw.splitlines():
        if "=" in ln:
            k, vv = ln.split("=", 1)
            d[k] = vv
    return d


def svc_control(action):
    run(["systemctl", action, SVC])


def update_sub():
    return run(["/usr/local/bin/update-mihomo-sub.sh"])


if __name__ == "__main__":
    H = make_handler(svc_status, svc_control, update_sub)
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    print(f"Mihomo Web 面板: http://127.0.0.1:{PORT}")
    srv.serve_forever()