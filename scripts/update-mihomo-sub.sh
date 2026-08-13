#!/usr/bin/env bash

SUB_URL="https://your-subscription-url.com/link"
CONFIG_PATH="/etc/mihomo/config.yaml"
TEMP_RAW="/etc/mihomo/config.yaml.sub"
TEMP_FINAL="/etc/mihomo/config.yaml.tmp"
API_URL="http://127.0.0.1:9090/configs"
SECRET=""

PATCH="/usr/local/bin/mihomo-patch.py"
MIHOMO="/usr/local/bin/mihomo"

echo "[$(date)] 开始拉取最新订阅..."
if ! curl -sL -A "clash-verge/v1.3.8" "$SUB_URL" -o "$TEMP_RAW"; then
    echo "[$(date)] 错误：订阅下载失败，保留原配置。"
    rm -f "$TEMP_RAW"
    exit 1
fi

if [ ! -s "$TEMP_RAW" ] || ! grep -q "^proxies:" "$TEMP_RAW"; then
    echo "[$(date)] 错误：订阅内容非法，保留原配置。"
    rm -f "$TEMP_RAW"
    exit 1
fi

python3 "$PATCH" "$TEMP_RAW" > "$TEMP_FINAL" || { echo "[$(date)] 错误：本地定制补丁失败，保留原配置。"; exit 1; }

if "$MIHOMO" -t -f "$TEMP_FINAL" -d /etc/mihomo >/dev/null 2>&1; then
    mv "$TEMP_FINAL" "$CONFIG_PATH"
    rm -f "$TEMP_RAW"
    echo "[$(date)] 配置更新成功（含节点优选取向 + TUN）。"

    if systemctl is-active --quiet mihomo; then
        echo "[$(date)] 正在通知 Mihomo 热加载新配置..."
        if [ -n "$SECRET" ]; then
            curl -s -X PUT "$API_URL" -H "Authorization: Bearer $SECRET" -H "Content-Type: application/json" -d "{\"path\": \"$CONFIG_PATH\"}" || true
        else
            curl -s -X PUT "$API_URL" -H "Content-Type: application/json" -d "{\"path\": \"$CONFIG_PATH\"}" || true
        fi
        echo ""
        echo "[$(date)] 配置更新并热加载完成。"
    fi
else
    echo "[$(date)] 错误：补丁后配置校验失败，保留原配置。"
    rm -f "$TEMP_FINAL" "$TEMP_RAW"
    exit 1
fi