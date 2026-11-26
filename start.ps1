# t2x-suite unified launcher: starts Novel Studio + T2VN (with embedded T2C) + Portal
# and injects SUITE_URL / NS_URL / T2VN_URL (plus optional shared defaults).
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$cfgPath = Join-Path $root "suite.json"
if (-not (Test-Path $cfgPath)) {
    Write-Host "[error] suite.json not found at $cfgPath" -ForegroundColor Red
    exit 1
}
$cfg = Get-Content -Raw -Encoding UTF8 $cfgPath | ConvertFrom-Json

# Optional local override (gitignored): suite.local.json
$localCfgPath = Join-Path $root "suite.local.json"
if (Test-Path $localCfgPath) {
    $localCfg = Get-Content -Raw -Encoding UTF8 $localCfgPath | ConvertFrom-Json
    foreach ($prop in $localCfg.PSObject.Properties) {
        if ($cfg.PSObject.Properties[$prop.Name] -and $prop.Value -is [PSCustomObject] -and $cfg.$($prop.Name) -is [PSCustomObject]) {
            foreach ($sub in $prop.Value.PSObject.Properties) {
                $cfg.$($prop.Name) | Add-Member -NotePropertyName $sub.Name -NotePropertyValue $sub.Value -Force
            }
        } else {
            $cfg | Add-Member -NotePropertyName $prop.Name -NotePropertyValue $prop.Value -Force
        }
    }
}

$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
$env:NS_URL = ($cfg.novel_studio.url).TrimEnd("/")
$env:T2VN_URL = ($cfg.t2vn.url).TrimEnd("/")
if ($cfg.portal -and $cfg.portal.url) {
    $env:SUITE_URL = ($cfg.portal.url).TrimEnd("/")
}
if ($cfg.shared) {
    if ($cfg.shared.library_dir) { $env:T2X_LIBRARY_DIR = [string]$cfg.shared.library_dir }
    if ($cfg.shared.comfyui_url) { $env:T2X_COMFYUI_URL = [string]$cfg.shared.comfyui_url }
    if ($cfg.shared.tagcomplete_csv) { $env:T2X_TAGCOMPLETE_CSV = [string]$cfg.shared.tagcomplete_csv }
}

function Test-UrlListening([string]$Url) {
    try {
        $uri = [Uri]$Url
        $client = New-Object System.Net.Sockets.TcpClient
        $ar = $client.BeginConnect($uri.Host, $uri.Port, $null, $null)
        $ok = $ar.AsyncWaitHandle.WaitOne(300)
        if ($ok -and $client.Connected) { $client.Close(); return $true }
        $client.Close()
        return $false
    } catch {
        return $false
    }
}

$started = New-Object System.Collections.ArrayList

function Start-ServiceEntry($entry) {
    if (-not $entry -or -not $entry.url) { return }
    if (Test-UrlListening $entry.url) {
        Write-Host "[skip] $($entry.name) already listening at $($entry.url)" -ForegroundColor Yellow
        return
    }
    if (-not (Test-Path $entry.python)) {
        Write-Host "[error] Python not found for $($entry.name): $($entry.python)" -ForegroundColor Red
        return
    }
    Write-Host "[start] $($entry.name) -> $($entry.url)" -ForegroundColor Cyan
    $proc = Start-Process -FilePath $entry.python `
        -ArgumentList $entry.args `
        -WorkingDirectory $entry.dir `
        -PassThru -NoNewWindow
    [void]$started.Add(@{ Name = $entry.name; Proc = $proc; Url = $entry.url })
}

try {
    Start-ServiceEntry $cfg.novel_studio
    Start-ServiceEntry $cfg.t2vn

    # Start t2x-suite Portal if portal/server.py exists
    $portalScript = Join-Path $root "portal\server.py"
    if ($cfg.portal -and $cfg.portal.url -and (Test-Path $portalScript)) {
        $portalPy = $cfg.novel_studio.python
        if (-not (Test-Path $portalPy)) { $portalPy = $cfg.t2vn.python }
        if (-not (Test-Path $portalPy)) { $portalPy = "python" }
        $portalUri = [Uri]$cfg.portal.url
        $portalEntry = [PSCustomObject]@{
            name   = $cfg.portal.name
            dir    = $root
            python = $portalPy
            args   = @($portalScript, "--host", $portalUri.Host, "--port", [string]$portalUri.Port)
            url    = $cfg.portal.url
        }
        Start-ServiceEntry $portalEntry
    }

    # Wait up to 20s for services to start listening
    $deadline = (Get-Date).AddSeconds(20)
    foreach ($svc in $started) {
        while ((Get-Date) -lt $deadline) {
            if ($svc.Proc.HasExited) {
                Write-Host "[error] $($svc.Name) exited early (code $($svc.Proc.ExitCode))" -ForegroundColor Red
                break
            }
            if (Test-UrlListening $svc.Url) {
                Write-Host "[ready] $($svc.Name) -> $($svc.Url)" -ForegroundColor Green
                break
            }
            Start-Sleep -Milliseconds 400
        }
    }

    if ($cfg.open_browser) {
        foreach ($key in $cfg.open_targets) {
            $u = $cfg.$key.url
            if ($u -and (Test-UrlListening $u)) {
                Start-Process $u
            }
        }
    }

    Write-Host ""
    Write-Host "t2x-suite running:" -ForegroundColor Green
    if ($cfg.portal -and $cfg.portal.url) {
        Write-Host "  Portal       : $($cfg.portal.url)"
    }
    Write-Host "  Novel Studio : $($cfg.novel_studio.url)"
    Write-Host "  T2VN / T2C   : $($cfg.t2vn.url)"
    Write-Host "Press Ctrl+C to stop all services." -ForegroundColor Gray

    while ($true) {
        Start-Sleep -Seconds 1
        $alive = @($started | Where-Object { -not $_.Proc.HasExited })
        if ($started.Count -gt 0 -and $alive.Count -eq 0) {
            Write-Host "[info] all child processes have exited." -ForegroundColor Yellow
            break
        }
    }
} finally {
    foreach ($svc in $started) {
        if (-not $svc.Proc.HasExited) {
            Write-Host "[stop] $($svc.Name) (PID $($svc.Proc.Id))" -ForegroundColor Gray
            Stop-Process -Id $svc.Proc.Id -Force -ErrorAction SilentlyContinue
        }
    }
}
