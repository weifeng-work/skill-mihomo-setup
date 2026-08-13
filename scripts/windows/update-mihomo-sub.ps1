#Requires -Version 5.1
# Windows equivalent of update-mihomo-sub.sh.
# Pulls the subscription, applies mihomo-patch.py customizations, validates,
# swaps config.yaml in, then hot-reloads via the REST API (no restart needed).
# Designed to run daily via a scheduled task and on demand by the Agent.
# Makes NO privileged/system changes beyond writing files under $WorkDir.

param(
    [string]$SubscriptionUrl = $env:SUB_URL,
    [string]$ConfigPath      = "C:\ProgramData\mihomo\config.yaml",
    [string]$WorkDir         = "C:\ProgramData\mihomo",
    [string]$Secret          = $env:MIHOMO_SECRET
)

$ErrorActionPreference = "Stop"
$LogFile    = Join-Path $WorkDir "update.log"
$TEMP_RAW   = Join-Path $WorkDir "config.yaml.sub"
$TEMP_FINAL = Join-Path $WorkDir "config.yaml.tmp"
$ApiUrl     = "http://127.0.0.1:9090/configs"
$Patch      = Join-Path $WorkDir "mihomo-patch.py"
$Mihomo     = Join-Path $WorkDir "bin\mihomo.exe"

function Log([string]$msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
    Write-Output $line
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
}

if (-not $SubscriptionUrl -or $SubscriptionUrl -match "your-subscription-url") {
    Log "错误：未提供订阅链接（SubscriptionUrl / env SUB_URL）。保留原配置。"
    exit 1
}
if (-not (Test-Path $Patch))  { Log "错误：找不到补丁脚本 $Patch。";  exit 1 }
if (-not (Test-Path $Mihomo)) { Log "错误：找不到 $Mihomo。"; exit 1 }

$python = $null
if (Get-Command python.exe -ErrorAction SilentlyContinue) { $python = "python.exe" }
elseif (Get-Command py.exe -ErrorAction SilentlyContinue) { $python = "py.exe" }
else { Log "错误：未找到 Python（mihomo-patch.py 需要）。"; exit 1 }

Log "开始拉取最新订阅..."
& curl.exe -sL -A "clash-verge/v1.3.8" $SubscriptionUrl -o $TEMP_RAW
if ($LASTEXITCODE -ne 0) {
    Log "错误：订阅下载失败，保留原配置。"
    Remove-Item $TEMP_RAW -ErrorAction SilentlyContinue
    exit 1
}
if (-not (Test-Path $TEMP_RAW) -or (Get-Item $TEMP_RAW).Length -eq 0 -or
    -not (Select-String -Path $TEMP_RAW -Pattern "^proxies:" -Quiet)) {
    Log "错误：订阅内容非法，保留原配置。"
    Remove-Item $TEMP_RAW -ErrorAction SilentlyContinue
    exit 1
}

Log "应用本地定制补丁..."
& $python $Patch $TEMP_RAW -o $TEMP_FINAL
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $TEMP_FINAL)) {
    Log "错误：本地定制补丁失败，保留原配置。"
    exit 1
}

Log "校验补丁后配置..."
$null = & $Mihomo -t -f $TEMP_FINAL -d $WorkDir 2>&1
if ($LASTEXITCODE -ne 0) {
    Log "错误：配置校验失败，保留原配置。"
    Remove-Item $TEMP_FINAL, $TEMP_RAW -ErrorAction SilentlyContinue
    exit 1
}

Copy-Item -Path $TEMP_FINAL -Destination $ConfigPath -Force
Remove-Item $TEMP_FINAL, $TEMP_RAW -ErrorAction SilentlyContinue
Log "配置更新成功（含节点优选取向 + TUN）。"

if (Get-Service mihomo -ErrorAction SilentlyContinue) {
    Log "正在通知 Mihomo 热加载新配置..."
    $headers = @{ "Content-Type" = "application/json" }
    if ($Secret) { $headers["Authorization"] = "Bearer $Secret" }
    try {
        $body = @{ path = $ConfigPath } | ConvertTo-Json
        Invoke-RestMethod -Method Put -Uri $ApiUrl -Headers $headers -Body $body -TimeoutSec 10 | Out-Null
        Log "配置更新并热加载完成。"
    } catch {
        Log "警告：热加载失败（API 不可达），配置已就位，服务重启后生效。"
    }
}
