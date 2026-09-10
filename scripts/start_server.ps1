# BasketIQ serverini qaldırır — Windows Task Scheduler üçün.
#
# NİYƏ AYRICA SKRIPT, NİYƏ BİRBAŞA uvicorn?
# İki səbəb var və hər ikisi ölçülüb:
#
# 1. PORT 8000 PAYLAŞILIR. Docker-in `fastapi-backend` konteyneri (başqa
#    layihə) `0.0.0.0:8000`-i tutur. Biz `127.0.0.1:8000`-ə bind oluruq və
#    daha dəqiq bind olduğumuz üçün qalib gəlirik. Amma server ARTIQ
#    işləyirsə, ikinci nüsxə qaldırmaq mənasızdır - bind xətası verər.
#    Ona görə əvvəlcə yoxlanılır.
#
# 2. GÖRÜNMƏZ İŞLƏMƏLİDİR. Task Scheduler `uvicorn.exe`-ni birbaşa çağırsa,
#    hər girişdə konsol pəncərəsi açılır. `-WindowStyle Hidden` bunu
#    qarşılayır.
#
# ƏL İLƏ İŞLƏTMƏK: powershell -ExecutionPolicy Bypass -File scripts\start_server.ps1

$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $PSScriptRoot
$Uvicorn = Join-Path $Root '.venv\Scripts\uvicorn.exe'
$LogOut = Join-Path $env:TEMP 'basketiq_server.log'
$LogErr = Join-Path $env:TEMP 'basketiq_server.err.log'
$PidFile = Join-Path $env:TEMP 'basketiq_server.pid'

# --- Artıq işləyirmi? ---
# YALNIZ 127.0.0.1 yoxlanılır: `0.0.0.0:8000` Docker-indir və onun olması
# bizim serverin işləməsi demək DEYİL. Bu fərqi nəzərə almasaq, skript
# «onsuz da işləyir» deyib heç nə etməz və sabah 07:00-da n8n boş yerə
# Docker konteynerinə düşərdi.
$listener = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
            Where-Object { $_.LocalAddress -eq '127.0.0.1' }

if ($listener) {
    "BasketIQ artiq isleyir (PID {0})" -f $listener.OwningProcess
    exit 0
}

if (-not (Test-Path $Uvicorn)) {
    Write-Error "uvicorn tapilmadi: $Uvicorn  (virtual muhit qurulubmu?)"
    exit 1
}

$proc = Start-Process -FilePath $Uvicorn `
    -ArgumentList 'app.main:app', '--host', '127.0.0.1', '--port', '8000' `
    -WorkingDirectory $Root `
    -WindowStyle Hidden `
    -PassThru `
    -RedirectStandardOutput $LogOut `
    -RedirectStandardError $LogErr

$proc.Id | Out-File $PidFile -Encoding ascii
"BasketIQ qaldirildi (launcher PID {0})" -f $proc.Id
