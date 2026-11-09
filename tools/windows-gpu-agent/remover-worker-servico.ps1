#requires -RunAsAdministrator
$TaskName = "AnimaStudio3D-RX580-Worker"
Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
$DataDir = Join-Path $env:ProgramData "AnimaStudio3D\RX580Worker"
if (Test-Path $DataDir) { Remove-Item -Path $DataDir -Recurse -Force }
Write-Host "Worker automático removido." -ForegroundColor Green
