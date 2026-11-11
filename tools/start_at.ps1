# Чекає до вказаного часу і запускає бота. Скасувати: створити файл D:\Starfield\bot\CANCEL_WAIT
param([string]$At = "01:03")
$target = [datetime]::ParseExact($At, "HH:mm", $null)
if ($target -le (Get-Date)) { $target = $target.AddDays(1) }
$log = "D:\Starfield\bot\work\log.txt"
Add-Content $log "$(Get-Date -Format HH:mm:ss) waiter: bot will start at $target"
while ((Get-Date) -lt $target) {
    if (Test-Path "D:\Starfield\bot\CANCEL_WAIT") {
        Remove-Item "D:\Starfield\bot\CANCEL_WAIT"
        Add-Content $log "$(Get-Date -Format HH:mm:ss) waiter: cancelled"
        exit
    }
    Start-Sleep -Seconds 30
}
Start-Process -FilePath "D:\Starfield\bot\run_now.bat" -WindowStyle Minimized
