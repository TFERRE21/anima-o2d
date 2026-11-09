$ErrorActionPreference = "Stop"
$Server = Read-Host "URL do painel (Enter para usar o endereço padrão)"
if (-not $Server) { $Server = "https://animacao2d.vps11710.panel.icontainer.work" }
$Token = Read-Host "Token ANIMA_WORKER_TOKEN configurado na VPS"
if (-not $Token) { throw "O token é obrigatório." }
$Blender = "$env:ProgramFiles\Blender Foundation\Blender 5.2\blender.exe"
if (-not (Test-Path $Blender)) { $Blender = Read-Host "Caminho completo do blender.exe" }
$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) { throw "Python 3 não encontrado. Instale Python 3.10+ e marque Add Python to PATH." }
$env:ANIMA_WORKER_SERVER = $Server.TrimEnd("/")
$env:ANIMA_WORKER_TOKEN = $Token
$env:ANIMA_BLENDER_PATH = $Blender
$env:ANIMA_SCENE_SCRIPT = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\backend\app\blender_scene.py"))
$env:ANIMA_WORKER_ID = $env:COMPUTERNAME + "-RX580"
Write-Host "Conectando trabalhador RX 580 ao Anima Studio..." -ForegroundColor Cyan
& $Python.Source (Join-Path $PSScriptRoot "worker.py")
