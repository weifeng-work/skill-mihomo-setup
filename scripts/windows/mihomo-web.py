#!/usr/bin/env python3
"""Mihomo Web 面板 - Windows 平台层。

仅含 Windows 专属逻辑：sc/nssm 服务探测与控制、PowerShell 订阅更新脚本。
其余（HTML/API 解析/路由）由 scripts/shared/mihomo_web_common.py 提供。
用法: python3 scripts/windows/mihomo-web.py   (http://127.0.0.1:8080)
"""
import os
import subprocess
import sys
from http.server import ThreadingHTTPServer

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)
sys.path.insert(0, os.path.join(_here, "..", "shared"))
from mihomo_web_common import PORT, make_handler

SVC = "Mihomo"


def run(cmd, sudo=False):
    c = ["sudo"] + cmd if sudo else cmd
    try:
        r = subprocess.run(c, capture_output=True, text=True, timeout=30)
        return (r.returncode, r.stdout + r.stderr)
    except Exception as e:
        return (1, str(e))


def svc_status():
    rc, q = run(["sc", "query", SVC])
    active = rc == 0 and "RUNNING" in q
    rc2, c = run(["sc", "qc", SVC])
    auto = rc2 == 0 and any(
        ln.strip().startswith("START_TYPE") and "AUTO_START" in ln
        for ln in c.splitlines()
    )
    return {"ActiveState": "active" if active else "inactive",
            "NRestarts": "?",
            "UnitFileState": "enabled" if auto else "disabled"}


def svc_control(action):
    if action == "start":
        run(["nssm", "start", SVC])
    elif action == "stop":
        run(["nssm", "stop", SVC])
    elif action == "enable":
        run(["sc", "config", SVC, "start=", "auto"])
    elif action == "disable":
        run(["sc", "config", SVC, "start=", "demand"])


def update_sub():
    return run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", r"C:\ProgramData\mihomo\update-mihomo-sub.ps1"])


if __name__ == "__main__":
    H = make_handler(svc_status, svc_control, update_sub)
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    print(f"Mihomo Web 面板: http://127.0.0.1:{PORT}")
    srv.serve_forever()