param(
    [string]$BlenderPath = "",
    [string]$OutputDirectory = "$PSScriptRoot\..\reports"
)

$ErrorActionPreference = "Stop"
$OutputDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

Write-Host "=== ANIMA STUDIO 3D | Diagnostico RX 580 ===" -ForegroundColor Cyan
Write-Host "Windows: $([System.Environment]::OSVersion.VersionString)"
Write-Host ""

$gpus = Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion, DriverDate, AdapterRAM, VideoModeDescription
$gpus | Format-List
$gpuText = ($gpus | Out-String)
if ($gpuText -notmatch "RX 580|Radeon RX 5") {
    Write-Warning "Nao encontrei RX 580 pelo nome. Confira o driver e o Gerenciador de Dispositivos."
}

if (-not $BlenderPath) {
    $cmd = Get-Command blender.exe -ErrorAction SilentlyContinue
    if ($cmd) { $BlenderPath = $cmd.Source }
}
if (-not $BlenderPath) {
    $candidates = @(
        "$env:ProgramFiles\Blender Foundation\Blender 5.2\blender.exe",
        "$env:ProgramFiles\Blender Foundation\Blender 5.1\blender.exe",
        "$env:ProgramFiles\Blender Foundation\Blender 4.5\blender.exe",
        "$env:ProgramFiles\Blender Foundation\Blender 4.4\blender.exe",
        "$env:ProgramFiles\Blender Foundation\Blender 4.3\blender.exe",
        "$env:ProgramFiles\Blender Foundation\Blender 4.2\blender.exe"
    )
    $BlenderPath = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $BlenderPath -or -not (Test-Path $BlenderPath)) {
    throw "Blender nao encontrado. Instale o Blender para Windows e rode novamente, ou informe -BlenderPath 'C:\caminho\blender.exe'."
}

$probe = Join-Path $PSScriptRoot "gpu_probe.py"
$json = Join-Path $OutputDirectory "anima-rx580-probe.json"
Write-Host "Blender: $BlenderPath"
Write-Host "Executando teste Eevee/OpenGL 640x360..."
& $BlenderPath --background --factory-startup --python $probe -- --output $json
$exitCode = $LASTEXITCODE
Write-Host ""
if (Test-Path $json) {
    Get-Content $json -Raw
}
if ($exitCode -ne 0) {
    throw "O teste do Blender falhou (codigo $exitCode). Veja o relatorio acima."
}
Write-Host "Teste concluido. Envie o arquivo: $json" -ForegroundColor Green
