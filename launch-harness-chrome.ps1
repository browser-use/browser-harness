# Launch the dedicated "harness Chrome" — a separate Chrome instance with its own
# profile and CDP enabled on a fixed port. Safe to run repeatedly: if Chrome is
# already up on the port, this is a no-op.
param(
  [int]$Port = 9223,
  [string]$ProfileDir = "$env:LOCALAPPDATA\browser-harness\chrome-profile",
  [string]$ChromeExe = "C:\Program Files\Google\Chrome\Application\chrome.exe"
)

$ErrorActionPreference = "Stop"

$alreadyUp = $false
try {
  $null = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/json/version" -UseBasicParsing -TimeoutSec 2
  $alreadyUp = $true
} catch {}

if ($alreadyUp) {
  Write-Host "harness Chrome already up on 127.0.0.1:$Port"
  exit 0
}

if (-not (Test-Path $ChromeExe)) { throw "Chrome not found at $ChromeExe" }
if (-not (Test-Path $ProfileDir)) { New-Item -ItemType Directory -Path $ProfileDir -Force | Out-Null }

Start-Process $ChromeExe -ArgumentList `
  "--user-data-dir=$ProfileDir", `
  "--remote-debugging-port=$Port", `
  "--no-first-run", `
  "--no-default-browser-check", `
  "about:blank"

# Wait for CDP to be live.
$deadline = (Get-Date).AddSeconds(20)
while ((Get-Date) -lt $deadline) {
  try {
    $null = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/json/version" -UseBasicParsing -TimeoutSec 1
    Write-Host "harness Chrome up on 127.0.0.1:$Port (profile: $ProfileDir)"
    exit 0
  } catch { Start-Sleep -Milliseconds 300 }
}
throw "Chrome launched but CDP did not come up on 127.0.0.1:$Port"
