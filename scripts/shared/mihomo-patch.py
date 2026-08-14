#!/usr/bin/env python3
"""Patch mihomo config: auto-select node priority (US > SG > TW > JP > HK, last) +
TUN + sniffer + fake-ip DNS, preserving the subscription's own nameservers.

Writes to the file given by -o/--output (utf-8) to avoid encoding corruption when the
process is piped through PowerShell; falls back to stdout with force-UTF-8 (fixes the
GBK UnicodeEncodeError seen on Chinese Windows for emoji group names).
"""
import argparse
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

INJECT_TUN = {
    "enable": True,
    "stack": "gvisor",
    "auto-route": True,
    "auto-detect-interface": True,
    "dns-hijack": ["any:53"],
    "route-address": ["0.0.0.0/0", "::/0"],
    "route-exclude-address": [
        "224.0.0.251/32",
        "224.0.0.252/32",
        "255.255.255.255/32",
        "ff02::fb/128",
        "ff02::1:3/128",
        "ff02::1/128",
    ],
}

INJECT_SNIFFER = {
    "enable": True,
    "force-dns-mapping": True,
    "parse-pure-ip": True,
    "sniff": {
        "HTTP": {
            "ports": [80, 8080, 8880, 2052, 2082, 2086, 2095],
            "override-destination": True,
        },
        "TLS": {"ports": [443, 8443, 2053, 2083, 2087, 2096]},
        "QUIC": {"ports": [443, 8443]},
    },
    "skip-domain": ["+.push.apple.com", "Mijia Cloud"],
}

FAKE_IP_FILTER = [
    "*.lan",
    "*.local",
    "+.msftconnecttest.com",
    "+.msftncsi.com",
    "localhost.ptlogin2.qq.com",
    "dns.msftncsi.com",
    "*.time.edu.cn",
    "*.ntp.org.cn",
    "+.market.xiaomi.com",
]

DEFAULT_FALLBACK = ["tls://8.8.8.8", "tls://1.1.1.1", "tls://dns.google"]
DEFAULT_FALLBACK_FILTER = {"geoip": True, "geoip-code": "CN", "ipcidr": ["240.0.0.0/4"]}


def merge_lists(base, extra):
    return list(dict.fromkeys(base + extra))


def patch(cfg):
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

    cfg.setdefault("tun", {}).update(INJECT_TUN)
    cfg["tun"] = dict(INJECT_TUN, **cfg["tun"])

    cfg.setdefault("sniffer", {}).update(INJECT_SNIFFER)
    cfg["sniffer"] = dict(INJECT_SNIFFER, **cfg["sniffer"])

    dns = dict(cfg.get("dns") or {}, enable=True)
    dns["enhanced-mode"] = "fake-ip"
    dns.setdefault("fake-ip-range", "198.18.0.1/16")
    dns["fake-ip-filter"] = merge_lists(dns.get("fake-ip-filter", []), FAKE_IP_FILTER)
    dns["fallback"] = merge_lists(dns.get("fallback", []), DEFAULT_FALLBACK)
    dns["fallback-filter"] = {**DEFAULT_FALLBACK_FILTER, **(dns.get("fallback-filter") or {})}
    cfg["dns"] = dns

    return cfg


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("src", nargs="?", default="/etc/mihomo/config.yaml",
                    help="input mihomo YAML (subscription or existing config)")
    ap.add_argument("-o", "--output", default=None,
                    help="write patched YAML to this file (utf-8). Default: stdout.")
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.src, encoding="utf-8"))
    cfg = patch(cfg)
    out = yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False, default_flow_style=False)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out)
    else:
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
        sys.stdout.write(out)