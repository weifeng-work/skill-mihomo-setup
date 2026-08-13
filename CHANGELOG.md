# Changelog / 修复日志

记录 `skill-mihomo-setup` 针对 GitHub issues #1-#6 的修复明细（根因 → 修复 → 验证）。

---

## issue #1 / #3 — 订阅 `sniffer` 与 fake-ip DNS 缺失

**根因**: 原始 `mihomo-patch.py` 只注入订阅本身，未写入 `sniffer:` 段与 fake-ip DNS 配置，导致域名嗅探与应用商店/TUN 域名解析异常。

**修复** (`scripts/shared/mihomo-patch.py` 重写):
- 注入 `sniffer:` 段（enable + force-dns-mapping + snap-dns）。
- fake-ip DNS：`dns.enhanced-mode: fake-ip`、`fake-ip-range`、`fake-ip-filter`。
- 兜底 DNS：`fallback: [tls://8.8.8.8, tls://1.1.1.1, tls://dns.google]`。
- `fallback-filter: geoip: CN`。
- 保留订阅原有 `nameserver`，避免覆盖用户自定义。

**验证**: `python3 -m py_compile` 通过；用合成订阅跑通注入，输出含 sniffer/fake-ip DNS 字段。

---

## issue #2 / #4 — UTF-8 编码乱码

**根因**: `subprocess` 管道在非 UTF-8 locale 下输出被解码为乱码，污染生成的 `config.yaml`。

**修复**:
- `mihomo-patch.py` 增加 `-o/--output` 参数，直接以 UTF-8 写文件；脚本兜底 `sys.stdout.reconfigure(encoding="utf-8")`。
- `scripts/linux/update-mihomo-sub.sh`（行 26）与 `scripts/windows/update-mihomo-sub.ps1` 均已改为 `-o` 调用。
- ps1 不再走 PowerShell 管道重定向，避免二次编码。

**验证**: `bash -n` / ps1 AST 校验通过；`mihomo-patch.py -o` 直写文件内容无乱码。

---

## issue #5 — Windows 资产下载地址 404

**根因**: SKILL.md 引用的 wintun/nssm GitHub release 链接全部 404（官方不在 GitHub 发布）。

**修复** (SKILL.md Windows 章节 + 新增 `scripts/shared/fetch-assets.py`):
- wintun 改用官方 `https://www.wintun.net/builds/wintun-0.14.1.zip`（~750 KB，内部 `wintun/bin/amd64/wintun.dll`）。
- nssm 改用官方 `https://nssm.cc/release/nssm-2.24.zip`（~350 KB，`ns/nssm-2.24/win64/nssm.exe`）。
- 新增 `fetch-assets.py`：`--os linux|windows`、`--dir/--bin-dir/--cpu avx2|compatible/--version/--force`，多源 fallback（GitHub 直连 → GFW 镜像），min_size + magic 校验、禁覆盖坏文件、可执行位 755。
- SKILL.md 补充下载后校验说明；注明引擎与 wintun/nssm 因 GFW 不可直连时通过脚本镜像 fallback。

**验证**: Linux 模式实测成功（mihomo ~29 MB ELF + geoip/geosite 约 12.8 MB）；wintun/nssm 官方 URL `curl` 实测 200，zip 规格与 issue 描述一致。

---

## issue #6 — Windows 面板假报“已断开连接” + 控制按钮失效

**根因**: `mihomo-web.py` 的 `status()` 与 `do_POST` 共 7 处硬编码 `systemctl`，Windows 无 systemctl 导致状态误判为 off，开始/停止/自启按钮全部失效。

**修复** (跨平台服务层，单文件 → 平台分层重构):
- 第一轮：`mihomo-web.py` 内加 `IS_WIN` / `SVC` 判定与 `win_svc_query()`、`svc_status()`、`svc_control()`、`update_sub()` 跨平台分支（Linux systemctl / Windows sc+nssm+powershell）。
- 第二轮（彻底解耦，按用户建议）：面板拆为共享核心 + 两平台薄层：
  - `scripts/shared/mihomo_web_common.py` — 平台无关：HTML/JS UI、`hamo`/`probe_node`、`status()` 数据解析、`make_handler(svc_status, svc_control, update_sub)` HTTP 路由器（do_GET/do_POST，含 mode PATCH）。
  - `scripts/linux/mihomo-web.py` — 仅 systemctl 服务层 + `update-mihomo-sub.sh` 调用。
  - `scripts/windows/mihomo-web.py` — 仅 sc/nssm/powershell 服务层 + `update-mihomo-sub.ps1` 调用。
- 两个平台入口都按 `__file__` 相对路径注入 `sys.path`，平铺安装（Linux `/usr/local/bin`、Windows `C:\ProgramData\mihomo`）与仓库树内运行均可用。

**验证**: `python3 -m py_compile` 三文件通过；双平台单测（mock subprocess）断言 Windows 发 `sc query/qc`、`nssm stop/start`、`sc config start= auto|demand`、`powershell.exe update-mihomo-sub.ps1`；Linux 发 `systemctl show/enable/disable`、`update-mihomo-sub.sh`；do_GET `/api/status` 与 do_POST stop/start/disable/enable/update 全动作经共享路由器正确分发到平台层；**真机端到端**：本机已安装新架构到 `/usr/local/bin` 并重启 `mihomo-web` systemd 服务，`/api/status` 返回 `service=active/enabled/mode=rule`、health=ok，`do_POST start` 使 mihomo 恢复 active。

---

## 备注
- 本机 `/etc/mihomo/config.yaml` 为真实订阅；仓库内不含任何私有订阅 token（副本用占位符）。
- CPU 无 AVX2 → mihomo 采用 `-compatible` 构建。
