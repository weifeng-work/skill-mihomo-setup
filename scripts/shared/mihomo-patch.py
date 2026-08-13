#!/usr/bin/env python3
"""Patch mihomo config: auto-select node priority (US > SG > TW > JP, no HK) + TUN."""
import sys
import yaml


def country(name):
    if any(k in name for k in ("香港", "Hong Kong", "HongKong")) or name.startswith("\U0001F1ED\U0001F1F0"):
        return "HK"
    if any(k in name for k in ("美国", "United States", "USA", "US ")) or name.startswith("\U0001F1FA\U0001F1F8"):
        return "US"
    if any(k in name for k in ("新加坡", "Singapore", "SG ")) or name.startswith("\U0001F1F8\U0001F1EC"):
        return "SG"
    if any(k in name for k in ("台湾", "Taiwan", "TW ")):
        return "TW"
    if any(k in name for k in ("日本", "Japan", "JP ")) or name.startswith("\U0001F1EF\U0001F1F5"):
        return "JP"
    return None


POOL_ORDER = ["US", "SG", "TW", "JP", "HK"]

if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "/etc/mihomo/config.yaml"
    cfg = yaml.safe_load(open(src, encoding="utf-8"))

    pools = {k: [] for k in POOL_ORDER}
    for p in cfg.get("proxies", []):
        c = country(p.get("name", ""))
        if c in pools:
            pools[c].append(p["name"])

    ordered = [n for k in POOL_ORDER for n in pools[k]]

    groups = cfg.setdefault("proxy-groups", [])
    main = None
    for g in groups:
        if g.get("name") == "🔰 选择节点":
            main = g
            g["type"] = "select"
            g["proxies"] = (["🚀 自动优选"] if ordered else []) + ordered + ["DIRECT"]

    if ordered and not any(g.get("name") == "🚀 自动优选" for g in groups):
        groups.insert(0, {
            "name": "🚀 自动优选",
            "type": "fallback",
            "proxies": ordered,
            "url": "https://www.gstatic.com/generate_204",
            "interval": 120,
            "tolerance": 500,
            "RequestTimeout": 500,
        })
    if main is None:
        cfg["proxy-groups"].insert(0, {
            "name": "🔰 选择节点",
            "type": "select",
            "proxies": (["🚀 自动优选"] if ordered else []) + ordered + ["DIRECT"],
        })

    cfg["tun"] = {
        "enable": True,
        "stack": "gvisor",
        "auto-route": True,
        "auto-detect-interface": True,
        "dns-hijack": ["any:53"],
        "route-address": ["0.0.0.0/0", "::/0"],
    }

    sys.stdout.write(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False, default_flow_style=False))