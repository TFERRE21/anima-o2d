<#
.SYNOPSIS
  Troca reversivel do UNet FP32 para FP16 no launcher ComfyUI-ZLUDA da RX 580.
.DESCRIPTION
  Mantem checkpoints, modelos, venv, ZLUDA e demais opcoes inalterados.
  Faz copia byte-a-byte antes da mudanca. FP16 pode ser incompatível
  com algumas combinacoes Polaris/ZLUDA; use -Modo restaurar nesse caso.
#>
param(
    [ValidateSet("verificar", "fp16", "restaurar")]
    [string]$Modo = "verificar",
    [string]$PastaComfy = "C:\ComfyUI-Zluda\ComfyUI-Zluda"
)
$ErrorActionPreference = "Stop"
$launcher = Join-Path $PastaComfy "comfyui.bat"
if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) {
    throw "Nao encontrei comfyui.bat em: $launcher"
}
$backups = @(Get-ChildItem -LiteralPath $PastaComfy -Filter "comfyui.bat.anima-backup-*" -File |
    Sort-Object LastWriteTime -Descending)
if ($Modo -eq "restaurar") {
    if ($backups.Count -eq 0) {
        throw "Nao existe backup criado por este script; nada foi alterado."
    }
    Copy-Item -LiteralPath $backups[0].FullName -Destination $launcher -Force
    Write-Host "Perfil original restaurado. Reinicie o processo ComfyUI para aplicar."
    exit 0
}

# Latin-1 is intentionally used as a reversible one-to-one mapping for bytes,
# preserving batch files originally saved as ANSI, OEM or UTF-8.
$codec = [System.Text.Encoding]::GetEncoding(28591)
$originalBytes = [System.IO.File]::ReadAllBytes($launcher)
$source = $codec.GetString($originalBytes)
$lines = $source -split "(\r\n|\n|\r)"
$relevant = $lines | Where-Object {
    $_ -match '(?i)--(force-fp32|fp32-unet|fp16-unet|novram|lowvram|cpu-vae|disable-cuda-malloc)'
}
Write-Host "=== ComfyUI-ZLUDA / RX580 ==="
Write-Host "Launcher:" $launcher
Write-Host "Argumentos encontrados:"
if ($relevant) {
    $relevant | ForEach-Object { Write-Host ($_ -replace '(?i)(api[_-]?key|token|password)\s*[=:]\s*\S+', '$1=<oculto>') }
} else {
    Write-Host "Nenhuma flag de precisao/VRAM encontrada neste .bat."
}
if ($Modo -eq "verificar") {
    Write-Host "Nenhuma alteracao realizada."
    exit 0
}

if ($source -match '(?i)--fp16-unet') {
    Write-Host "O launcher ja usa --fp16-unet. Nenhuma alteracao."
    exit 0
}
# Change only lines which are commands rather than REM or :: comments.
$changed = $false
for ($i = 0; $i -lt $lines.Count; $i++) {
    $line = $lines[$i]
    if ($line -match '^\s*(?i:rem\b|::)' -or $line -notmatch '(?i)--(force-fp32|fp32-unet)\b') {
        continue
    }
    $updated = $line -replace '(?i)--force-fp32\b', '--fp16-unet'
    $updated = $updated -replace '(?i)--fp32-unet\b', '--fp16-unet'
    $lines[$i] = $updated
    $changed = $true
}
if (-not $changed) {
    throw "Nao encontrei --force-fp32/--fp32-unet nas linhas ativas do .bat. Nao modifiquei o launcher; confira o argumento usado no seu iniciador personalizado."
}
$backup = Join-Path $PastaComfy ("comfyui.bat.anima-backup-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
[System.IO.File]::WriteAllBytes($backup, $originalBytes)
$updatedBytes = $codec.GetBytes([string]::Join("", $lines))
try {
    [System.IO.File]::WriteAllBytes($launcher, $updatedBytes)
} catch {
    [System.IO.File]::WriteAllBytes($launcher, $originalBytes)
    throw
}
Write-Host "Backup preservado:" $backup
Write-Host "UNet configurado para FP16 no launcher (mantido NOVRAM e CPU-VAE se ja existiam)."
Write-Host "IMPORTANTE: RX580/ZLUDA pode nao aceitar FP16. Se falhar:"
Write-Host "  .\perfil-rx580-zluda.ps1 -Modo restaurar"
Write-Host "Reinicie somente o ComfyUI. Nao reinstale PyTorch nem apague checkpoints."
