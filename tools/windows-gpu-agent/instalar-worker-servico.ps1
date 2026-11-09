#requires -RunAsAdministrator
$ErrorActionPreference = "Stop"
$Server = Read-Host "URL do Anima Studio [https://animacao2d.vps11710.panel.icontainer.work]"
if ([string]::IsNullOrWhiteSpace($Server)) { $Server = "https://animacao2d.vps11710.panel.icontainer.work" }
$Server = $Server.Trim().TrimEnd("/")
if ($Server -notmatch "^https://") { throw "Use a URL HTTPS pública do Anima Studio." }
$SecureToken = Read-Host "Token ANIMA_WORKER_TOKEN da VPS" -AsSecureString
if ($SecureToken.Length -lt 20) { throw "Token vazio ou muito curto." }
$Blender = Join-Path $env:ProgramFiles "Blender Foundation\Blender 5.2\blender.exe"
if (-not (Test-Path $Blender)) { $Blender = Read-Host "Caminho completo do blender.exe" }
if (-not (Test-Path $Blender)) { throw "Blender não encontrado." }
$PythonExe = $null
try {
    $candidate = (& py -3 -c "import sys; print(sys.executable)" 2>$null | Select-Object -First 1)
    if ($LASTEXITCODE -eq 0 -and $candidate -and (Test-Path $candidate.Trim())) { $PythonExe = $candidate.Trim() }
} catch {}
if (-not $PythonExe) {
    $cmd = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source -and (Test-Path $cmd.Source)) {
        $candidate = (& $cmd.Source -c "import sys; print(sys.executable)" 2>$null | Select-Object -First 1)
        if ($LASTEXITCODE -eq 0 -and $candidate -and (Test-Path $candidate.Trim())) { $PythonExe = $candidate.Trim() }
    }
}
if (-not $PythonExe) { throw "Python 3 não encontrado. Instale Python 3.10 ou superior." }
$PythonVersion = & $PythonExe -c "import sys; print('%d.%d' % sys.version_info[:2])"
$VersionParts = $PythonVersion.Trim().Split(".")
if ([int]$VersionParts[0] -lt 3 -or ([int]$VersionParts[0] -eq 3 -and [int]$VersionParts[1] -lt 10)) { throw "É necessário Python 3.10 ou superior. Encontrado: $PythonVersion" }
$WorkerDir = $PSScriptRoot
$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $WorkerDir "..\..\"))
$WorkerPy = Join-Path $WorkerDir "worker.py"
$ScenePy = Join-Path $RepoRoot "backend\app\blender_scene.py"
$Runner = Join-Path $WorkerDir "executar-worker-servico.ps1"
if (-not (Test-Path $WorkerPy) -or -not (Test-Path $ScenePy) -or -not (Test-Path $Runner)) { throw "Arquivos do worker incompletos. Extraia o repositório completo." }
Add-Type -AssemblyName System.Security
$Bstr = [IntPtr]::Zero
try {
    $Bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureToken)
    $PlainToken = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Bstr)
    $TokenBytes = [Text.Encoding]::UTF8.GetBytes($PlainToken)
    $Entropy = [Text.Encoding]::UTF8.GetBytes("AnimaStudio3D-RX580-Worker-v1")
    $Protected = [Security.Cryptography.ProtectedData]::Protect($TokenBytes, $Entropy, [Security.Cryptography.DataProtectionScope]::LocalMachine)
} finally {
    if ($Bstr -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Bstr) }
    Remove-Variable PlainToken -ErrorAction SilentlyContinue
}
$DataDir = Join-Path $env:ProgramData "AnimaStudio3D\RX580Worker"
New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
$ConfigPath = Join-Path $DataDir "worker-config.json"
$Config = @{ server=$Server; token_protected=[Convert]::ToBase64String($Protected); python=$PythonExe; blender=$Blender; worker_script=$WorkerPy; scene_script=$ScenePy; worker_id="$env:COMPUTERNAME-RX580" }
$Config | ConvertTo-Json -Depth 4 | Set-Content -Path $ConfigPath -Encoding UTF8
& icacls.exe $DataDir /inheritance:r /grant:r "*S-1-5-18:(OI)(CI)F" "*S-1-5-32-544:(OI)(CI)F" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Não foi possível proteger as permissões da configuração." }
$TaskName = "AnimaStudio3D-RX580-Worker"
$PowerShellExe = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$Arguments = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + $Runner + '"'
$Action = New-ScheduledTaskAction -Execute $PowerShellExe -Argument $Arguments -WorkingDirectory $WorkerDir
$Trigger = New-ScheduledTaskTrigger -AtStartup
$Principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Description "Anima Studio 3D RX580 render worker; starts at Windows boot without interactive login." -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName
Write-Host "Instalação concluída. Worker registrado para iniciar no boot sem login." -ForegroundColor Green
Write-Host "Logs: $DataDir\worker.log"
Write-Host "Verifique: Get-ScheduledTaskInfo -TaskName '$TaskName'"
Write-Host "Para remover: .\remover-worker-servico.ps1"
