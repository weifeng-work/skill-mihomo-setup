#!/usr/bin/env python3
"""Fetch every runtime asset the mihomo stack needs, on Linux or Windows.

Centralizes all download URLs, tries multiple sources per asset (GitHub direct +
GFW mirror prefix), validates each download (minimum size + magic bytes), and only
ever overwrites a destination with a file that passed validation — a failing source
(404 body, mirror outage) can never clobber a previously-good file.

Usage:
  python3 fetch-assets.py --os linux   --dir /etc/mihomo [--bin-dir /etc/mihomo]
  python3 fetch-assets.py --os windows --dir C:\\ProgramData\\mihomo

Options:
  --os linux|windows      target platform (default: linux)
  --dir PATH              assets directory (default: /etc/mihomo or C:\\ProgramData\\mihomo)
  --bin-dir PATH          where mihomo.exe / mihomo go (default: --dir / --dir\\bin)
  --cpu avx2|compatible   mihomo build variant (default: compatible — safest; avx2 = v3 build)
  --version VER           mihomo release tag, e.g. v1.18.7 (default: v1.18.7)
  --force                 re-download even if the target already exists and is valid

Exit code 0 = all assets present & valid; non-zero = at least one asset missing.
"""
import argparse
import gzip
import io
import os
import sys
import zipfile
import urllib.request

VERSION = "v1.18.7"
MIRROR = "https://ghfast.top/"  # prefix for GitHub-hosted assets behind the GFW

MIN = {
    "mihomo": 10 * 1024 * 1024,
    "geoip.metadb": 5 * 1024 * 1024,
    "geosite.dat": 1 * 1024 * 1024,
    "wintun": 100 * 1024,
    "nssm": 50 * 1024,
}


def gh(path_or_url):
    return path_or_url if path_or_url.startswith("http") else f"https://github.com/{path_or_url}"


def sources(urls):
    out = []
    for u in urls:
        out.append(u)
        if "github.com" in u:
            out.append(MIRROR + u)
    return list(dict.fromkeys(out))


def fetch(urls, min_size, magic=None):
    """Return validated bytes from the first source that works, else None."""
    ua =        {"User-Agent": "clash-verge/v1.3.8"}
    for u in sources(urls):
        for _ in range(3):
            try:
                req = urllib.request.Request(u, headers=ua)
                with urllib.request.urlopen(req, timeout=120) as r:
                    data = r.read()
                if len(data) < min_size:
                    print(f"  -> {u} too small ({len(data)} B), skip", file=sys.stderr)
                    break
                if magic and not data.startswith(magic):
                    print(f"  -> {u} bad magic, skip", file=sys.stderr)
                    break
                return data
            except Exception as e:
                print(f"  -> {u} (attempt {_ + 1}): {e}", file=sys.stderr)
    return None


def want(force, dst):
    if force:
        return True
    name = os.path.basename(dst).replace(".exe", "")
    if name == "wintun.dll":
        name = "wintun"
    if not os.path.exists(dst):
        return True
    return os.path.getsize(dst) < MIN[name]


def extract_zip_member(zdata, predicate, dst):
    with zipfile.ZipFile(io.BytesIO(zdata)) as z:
        for n in z.namelist():
            if predicate(n):
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with open(dst, "wb") as f:
                    f.write(z.read(n))
                return True
    return False


def put(data, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "wb") as f:
        f.write(data)
    try:
        os.chmod(dst, 0o755)
    except Exception:
        pass


def linux(args, d):
    cpu = "" if args.cpu == "avx2" else "-compatible"
    base = gh(f"MetaCubeX/mihomo/releases/download/{args.version}/mihomo-linux-amd64{cpu}-{args.version}.gz")
    gdata = gh(f"MetaCubeX/meta-rules-dat/releases/download/latest/")

    ok = True
    bin_d = args.bin_dir or d
    for rel, urls, dst, magic in [
        ("mihomo", [base], os.path.join(bin_d, "mihomo"), b"\x1f\x8b"),
        ("geoip.metadb", [gdata + "geoip.metadb"], os.path.join(d, "geoip.metadb"), None),
        ("geosite.dat", [gdata + "geosite.dat"], os.path.join(d, "geosite.dat"), None),
    ]:
        if not want(args.force, dst):
            print(f"[skip] {rel} already valid")
            continue
        blob = fetch(urls, MIN[rel], magic)
        if blob is None:
            print(f"[FAIL] {rel}", file=sys.stderr)
            ok = False
            continue
        data = gzip.decompress(blob) if rel == "mihomo" else blob
        put(data, dst)
        print(f"[ok] {rel} -> {dst} ({len(data)} B)")
    return ok


def windows(args, d):
    cpu = "" if args.cpu == "avx2" else "-compatible"
    zbase = gh(f"MetaCubeX/mihomo/releases/download/{args.version}/mihomo-windows-amd64{cpu}-{args.version}.zip")
    gdata = gh(f"MetaCubeX/meta-rules-dat/releases/download/latest/")
    bin_d = args.bin_dir or os.path.join(d, "bin")
    ok = True
    for rel, urls, dst, magic in [
        ("mihomo", [zbase], os.path.join(bin_d, "mihomo.exe"), b"PK\x03\x04"),
        ("geoip.metadb", [gdata + "geoip.metadb"], os.path.join(d, "geoip.metadb"), None),
        ("geosite.dat", [gdata + "geosite.dat"], os.path.join(d, "geosite.dat"), None),
        ("wintun", ["https://www.wintun.net/builds/wintun-0.14.1.zip"], os.path.join(d, "wintun.dll"), b"PK\x03\x04"),
        ("nssm", ["https://nssm.cc/release/nssm-2.24.zip"], os.path.join(bin_d, "nssm.exe"), b"PK\x03\x04"),
    ]:
        key = rel.replace(".exe", "")
        if not want(args.force, dst):
            print(f"[skip] {rel} already valid")
            continue
        blob = fetch(urls, MIN[key], magic)
        if blob is None:
            print(f"[FAIL] {rel}", file=sys.stderr)
            ok = False
            continue
        if rel == "mihomo":
            good = extract_zip_member(blob, lambda n: n.endswith("/mihomo.exe"), dst)
        elif rel == "wintun":
            good = extract_zip_member(blob, lambda n: "amd64" in n and n.endswith("wintun.dll"), dst)
        elif rel == "nssm":
            good = extract_zip_member(blob, lambda n: n.endswith("/nssm.exe"), dst)
        else:
            put(blob, dst)
            good = True
        if not good:
            print(f"[FAIL] {rel}: archive member not found", file=sys.stderr)
            ok = False
            continue
        print(f"[ok] {rel} -> {dst}")
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--os", choices=["linux", "windows"], default="linux")
    ap.add_argument("--dir")
    ap.add_argument("--bin-dir")
    ap.add_argument("--cpu", choices=["avx2", "compatible"], default="compatible")
    ap.add_argument("--version", default=VERSION)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    d = args.dir or ("C:\\ProgramData\\mihomo" if args.os == "windows" else "/etc/mihomo")
    ok = (windows if args.os == "windows" else linux)(args, d)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()