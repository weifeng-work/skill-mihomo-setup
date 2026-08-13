---
name: mihomo-setup
description: Use ONLY when the user wants to install, deploy, reconfigure, or troubleshoot a Mihomo (Clash Meta) proxy on Linux. Keywords: mihomo, clash, clash-meta, 代理, 科学上网, 订阅, 订阅链接, TUN, 透明代理, 节点优选, 热加载, proxy. Covers full turnkey deployment: binary install (incl. CPU-v3 and GFW workarounds), subscription auto-pull with hot reload, country-priority node selection, TUN global mode, systemd services, cron updates, and the web/terminal monitoring panels.
---

# Mihomo (Clash Meta) Turnkey Deployment

Deploy a fully automated, GUI-free Mihomo proxy daemon on Debian/Ubuntu-style Linux with:
subscription auto-pull + syntax-validated hot reload, country-priority auto node selection,
TUN transparent mode, systemctl services, cron updates, and a browser/terminal monitoring panel.

## Mandatory prerequisite (不满足不开始)

**Before ANY install step, obtain ONE of the following from the user — a Mihomo/Clash
proxy is impossible without it, so ask first and do not proceed if missing:**

1. A **subscription URL** (`https://.../link?...`) that returns a Clash/Mihomo YAML. The
   provider's link may need query params like `?clash=3&extend=1` to emit the right format.
2. A **valid ready-made YAML config** the user already has (their own config file), which
   will be installed as `/etc/mihomo/config.yaml` directly.

Validate before continuing:

```bash
# option 1: subscription URL
curl -sL -A "clash-verge/v1.3.8" "$SUB_URL" -o /tmp/opencode/sub.yaml
grep -qE "^port:|^socks-port:|^mixed-port:" /tmp/opencode/sub.yaml   # has a listen port
grep -q "^proxies:" /tmp/opencode/sub.yaml                            # has nodes
# option 2: existing YAML — an agent must read it and confirm proxies: + external-controller: exist
```

If NEITHER is available, explain to the user that a subscription URL or YAML is the
mandatory prerequisite (it contains the actual node/proxy servers) and stop — do not invent
placeholders or fabricate config.

## Running order

### 0. Prechecks (run first, adapt path if already installed)

```bash
uname -m                                   # arch (amd64/arm64)
echo "sudo: $(sudo -n true 2>/dev/null && echo OK || echo NO)"
command -v curl wget gunzip systemctl crontab
command -v mihomo || echo "mihomo not installed"
grep -o -m1 'avx2\|avx512' /proc/cpuinfo | sort -u   # v3 microarch check
```

- `mihomo -v` printing *"can only be run on AMD64 processors with v3"* ⟹ CPU is v1/v2: MUST use the **`-compatible`** binary variant (release asset `mihomo-linux-amd64-compatible-<ver>.gz`).
- If `curl github.com` returns `000` (GFW), fetch all GitHub-hosted assets through a proxy mirror such as **`https://ghfast.top/<full-github-url>`**. The direct subscription host is usually reachable.

### 1. Install binary

```bash
cd /tmp/opencode
curl -sL -o mihomo.gz "https://ghfast.top/https://github.com/MetaCubeX/mihomo/releases/download/v1.18.7/mihomo-linux-amd64-compatible-v1.18.7.gz"
gunzip -f mihomo.gz && file mihomo                      # must be ELF x86-64, statically linked
sudo install -m 755 mihomo /usr/local/bin/mihomo && mihomo -v
sudo mkdir -p /etc/mihomo
```

### 2. Initial config + geo data

```
sudo cp <downloaded-sub.yaml> /etc/mihomo/config.yaml
```

The subscription YAML references GeoIP/GeoSite that mihomo tries to download from GitHub (blocked).
Fetch them through the mirror once and drop them beside the config, or `mihomo -t` will fail:

```bash
cd /tmp/opencode
curl -sL -o geoip.metadb "https://ghfast.top/https://github.com/MetaCubeX/meta-rules-dat/releases/download/latest/geoip.metadb"
curl -sL -o geosite.dat  "https://ghfast.top/https://github.com/MetaCubeX/meta-rules-dat/releases/download/latest/geosite.dat"
sudo cp geoip.metadb geosite.dat /etc/mihomo/
sudo /usr/local/bin/mihomo -t -d /etc/mihomo   # must say "configuration file ... test is successful"
```

### 3. Local customization patch

Run `scripts/mihomo-patch.py` on the subscription YAML. It rewrites the config so that every
subscription update keeps your customizations. Current behavior (edit the script to change):

- Builds a `🚀 自动优选` fallback group with node order **US → SG → TW → JP → HK(last)** based on node-name/flag classification; no other countries.
- Re-points the subscription's main `🔰 选择节点` selector at that auto group + those nodes.
- Injects a `tun:` block (enable, gvisor stack, auto-route, auto-detect-interface, dns-hijack `any:53`).
- `RequestTimeout: 500` on the auto group = a node is considered dead when a health probe exceeds 500 ms, so fallback auto-moves to the next country/candidate. `interval: 120` = health-check cadence.

```bash
sudo install -m 755 scripts/mihomo-patch.py /usr/local/bin/mihomo-patch.py
python3 /usr/local/bin/mihomo-patch.py /etc/mihomo/config.yaml > /tmp/merged.yaml   # or feed the raw sub
sudo cp /tmp/merged.yaml /etc/mihomo/config.yaml
sudo /usr/local/bin/mihomo -t -d /etc/mihomo
```

`python3-yaml` is required: `sudo apt-get install -y python3-yaml`.
TUN also needs the `tun` kernel module and iptables: `sudo modprobe tun && sudo apt-get install -y iptables`.

### 4. Update script (keeps customizations forever)

Install `scripts/update-mihomo-sub.sh`. Its pipeline is:
**download fresh sub → `mihomo-patch.py` re-apply (preserves node policy + TUN) → `mihomo -t` validate → `mv` → API hot reload (`PUT /configs {"path":...}`)**.

Set `SUB_URL=` inside the script to the user's real subscription URL BEFORE installing.

```bash
sudo install -m 755 scripts/update-mihomo-sub.sh /usr/local/bin/update-mihomo-sub.sh
```

### 5. systemd services + cron

```bash
sudo cp scripts/mihomo.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now mihomo
systemctl is-active mihomo
curl -s http://127.0.0.1:9090/version                     # REST API up
sudo ss -tlnp | grep -E "7890|7891|9090"                  # http/socks/api listening
printf '0 4 * * * root /usr/local/bin/update-mihomo-sub.sh >> /var/log/mihomo-update.log 2>&1\n' | sudo tee /etc/cron.d/mihomo-update >/dev/null
```

### 6. Monitoring panels

Web panel (systemd service, listens 127.0.0.1:8080, health banner + stop/start/enable/disable/mode/update controls):

```bash
sudo install -m 755 scripts/mihomo-web.py /usr/local/bin/mihomo-web.py
sudo cp scripts/mihomo-web.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now mihomo-web
```

Terminal panel (curses, run as user: `mihomo-board`):

```bash
sudo install -m 755 scripts/mihomo-board /usr/local/bin/mihomo-board
```

Optional UX conveniences: `echo "127.0.0.1 mihomo.local" | sudo tee -a /etc/hosts` and a `.desktop`
launcher under `~/.local/share/applications` that runs `xdg-open http://mihomo.local:8080`.

### 7. End-to-end verification checklist

```bash
systemctl is-active mihomo
curl -s http://127.0.0.1:9090/proxies | jq -r '.proxies["🔰 选择节点"].now'   # should be 🚀 自动优选
curl -s http://127.0.0.1:9090/proxies | jq -r '.proxies["🚀 自动优选"].now'   # a US node when healthy
ip -br addr show dev Meta                                    # TUN iface after restart
curl -s --noproxy '*' --max-time 15 -o /dev/null -w "%{http_code}\n" https://www.google.com/generate_204  # 204 via TUN
# stop/start the web panel and re-check health transitions to 已断开连接
```

## Behaviors worth restating to the user

- **Hot reload:** updates never restart the process; existing TCP connections survive.
- **Dynamic subscription:** because every update re-runs the patch step, node-priority + TUN survive
  subscription refreshes (cron 04:00 or manual). If the provider renames nodes without the
  country keywords/flags used by `mihomo-patch.py`, re-classification silently drops them — tell the user.
- **Fallback vs url-test:** `fallback` honors list order (country priority); `url-test` always picks
  lowest latency. We use `fallback` + `RequestTimeout: 500` so a slow-but-alive US node (≥500 ms) still
  yields to the next one.
- **Kill switch / full-direct:** `sudo systemctl stop mihomo` tears TUN rules down cleanly → all traffic
  reverts to direct. Re-enable with `systemctl start mihomo`. Disable autostart with `systemctl disable mihomo`.
- **500 ms threshold** lives in `mihomo-patch.py` (RequestTimeout/tolerance); adjusting it requires
  re-patching + reload.

## Traps learned (historical)

- `addnstr` on wide-char (CJK/emoji) strings throws `_curses.error: addnwstr() returned ERR`; all panel
  rendering uses a `wcwidth`-based `put()` that clips by display column width.
- Never put `'\n'` inside a Python triple-quoted HTML template for the web panel — Python expands it
  into a real newline and breaks the embedded JS. Use `String.fromCharCode(10)` in the JS instead. Add
  `Cache-Control: no-store` to the panel's HTML responses so stale pages don't linger.
- The v3-CPU binary refuses to start on older CPUs; always confirm CPU flags before choosing the asset.