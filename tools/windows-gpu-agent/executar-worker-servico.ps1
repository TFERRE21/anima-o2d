$ErrorActionPreference = "Stop"
$DataDir = Join-Path $env:ProgramData "AnimaStudio3D\RX580Worker"
$ConfigPath = Join-Path $DataDir "worker-config.json"
$LogPath = Join-Path $DataDir "worker.log"
try {
    if (-not (Test-Path $ConfigPath)) { throw "Configuração não encontrada: $ConfigPath" }
    $Config = Get-Content -Raw -Path $ConfigPath | ConvertFrom-Json
    Add-Type -AssemblyName System.Security
    $Cipher = [Convert]::FromBase64String([string]$Config.token_protected)
    $Entropy = [Text.Encoding]::UTF8.GetBytes("AnimaStudio3D-RX580-Worker-v1")
    $TokenBytes = [Security.Cryptography.ProtectedData]::Unprotect($Cipher, $Entropy, [Security.Cryptography.DataProtectionScope]::LocalMachine)
    $Token = [Text.Encoding]::UTF8.GetString($TokenBytes)
    $env:ANIMA_WORKER_SERVER = [string]$Config.server
    $env:ANIMA_WORKER_TOKEN = $Token
    $env:ANIMA_BLENDER_PATH = [string]$Config.blender
    $env:ANIMA_SCENE_SCRIPT = [string]$Config.scene_script
    $env:ANIMA_WORKER_ID = [string]$Config.worker_id
    "[$(Get-Date -Format o)] Worker starting as $([Security.Principal.WindowsIdentity]::GetCurrent().Name)" | Add-Content -Path $LogPath -Encoding UTF8
    & ([string]$Config.python) ([string]$Config.worker_script) *>> $LogPath
    $ExitCode = $LASTEXITCODE
    "[$(Get-Date -Format o)] Worker exited with code $ExitCode" | Add-Content -Path $LogPath -Encoding UTF8
    exit $ExitCode
} catch {
    "[$(Get-Date -Format o)] FATAL: $($_.Exception.Message)" | Add-Content -Path $LogPath -Encoding UTF8
    exit 1
} finally {
    Remove-Item Env:ANIMA_WORKER_TOKEN -ErrorAction SilentlyContinue
    Remove-Variable Token, TokenBytes, Cipher -ErrorAction SilentlyContinue
}
