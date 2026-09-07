<#
  ProCare OS - unwedge a stalled eStock sync.   2026-08-30

  WHAT WENT WRONG (2026-08-29 23:06 -> 2026-08-30 02:45, 3h40m with no sync):
  Several ETL cycles were running at once against the ProCare database - the
  backend's own 5-minute thread plus three ad-hoc ones left over from an earlier
  debugging session (`python -c "... sync.run_once()"`, and two runs of
  .local-run/sync_offpeak.py). They took locks on gl_accounts and
  estock_raw_watermark in different orders, one of them went idle holding an
  exclusive lock, and every other cycle - including the backend's - queued behind
  it for ever, because SQL Server's default LOCK_TIMEOUT is "wait indefinitely".
  Eight orphaned SQLCMD sessions from the same session were caught in the pile-up.
  The mirror kept reporting `running: true, last_status: "ok"` throughout.

  WHAT THIS SCRIPT DOES
  1. KILLs only the orphaned SQL sessions (>30 min stuck, not the live backend).
  2. Terminates the orphaned OS processes behind them.
  3. Restarts the backend so the new guard code is loaded.

  NEVER TOUCHED: the `maua` login (that is the live eStock POS), SQL Agent,
  and any session belonging to the running backend.

  Run from the repo root:  powershell -ExecutionPolicy Bypass -File tools\unblock_sync.ps1
#>

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot

# --- 0. who is the live backend? ------------------------------------------
$backend = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
           Where-Object { $_.CommandLine -match 'run\.py' } |
           Select-Object -First 1
$backendPid = if ($backend) { [int]$backend.ProcessId } else { -1 }
Write-Host "Live backend PID: $backendPid" -ForegroundColor Cyan

# --- 1. clear the stuck SQL sessions --------------------------------------
$sql = @"
SET NOCOUNT ON;
DECLARE @sid int, @cmd nvarchar(50);
DECLARE c CURSOR FOR
  SELECT s.session_id
  FROM sys.dm_exec_sessions s
  WHERE s.is_user_process = 1
    AND s.session_id <> @@SPID
    AND s.login_name IN ('procare_app','procare_reader','$($env:COMPUTERNAME)\$($env:USERNAME)')
    AND ISNULL(s.host_process_id, -1) <> $backendPid
    AND DATEDIFF(second, s.last_request_start_time, GETDATE()) > 1800;
OPEN c; FETCH NEXT FROM c INTO @sid;
WHILE @@FETCH_STATUS = 0
BEGIN
  SET @cmd = N'KILL ' + CAST(@sid AS nvarchar(10));
  BEGIN TRY EXEC sp_executesql @cmd; PRINT 'killed session ' + CAST(@sid AS varchar(10)); END TRY
  BEGIN CATCH PRINT 'could not kill ' + CAST(@sid AS varchar(10)) + ': ' + ERROR_MESSAGE(); END CATCH
  FETCH NEXT FROM c INTO @sid;
END
CLOSE c; DEALLOCATE c;
"@
Write-Host "`n-- clearing stuck SQL sessions --" -ForegroundColor Cyan
sqlcmd -S localhost,1433 -E -d master -b -Q $sql

# --- 2. terminate the orphaned ETL / SQLCMD processes ----------------------
Write-Host "`n-- terminating orphaned sync processes --" -ForegroundColor Cyan
$cutoff = (Get-Date).AddMinutes(-30)
Get-CimInstance Win32_Process |
  Where-Object {
    $_.ProcessId -ne $backendPid -and $_.ProcessId -ne $PID -and
    $_.CreationDate -lt $cutoff -and
    ( ($_.Name -eq 'SQLCMD.EXE') -or
      ($_.Name -match '^python(w)?\.exe$' -and
       $_.CommandLine -match 'sync_offpeak|run_once|raw_mirror_offpeak_fill|count_remain') )
  } |
  ForEach-Object {
    Write-Host ("  terminating {0} {1}" -f $_.ProcessId, $_.Name)
    try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop } catch { Write-Host "    $_" }
  }

# --- 3. restart the backend so the new sync guard is loaded ---------------
Write-Host "`n-- restarting the backend --" -ForegroundColor Cyan
if ($backendPid -gt 0) { Stop-Process -Id $backendPid -Force -ErrorAction SilentlyContinue; Start-Sleep 3 }
Push-Location "$repo\src\backend"
Start-Process -FilePath 'python' -ArgumentList 'run.py' `
  -RedirectStandardOutput "$repo\.local-run\backend.log" `
  -RedirectStandardError  "$repo\.local-run\backend.err.log" `
  -WindowStyle Hidden
Pop-Location
Start-Sleep 12
try {
  $h = Invoke-RestMethod -Uri 'http://127.0.0.1:8100/api/health' -TimeoutSec 20
  Write-Host "`nbackend health: $($h.status)  (products: $($h.seeded_products))" -ForegroundColor Green
} catch {
  Write-Host "`nbackend did not answer yet - check .local-run\backend.log" -ForegroundColor Yellow
}
