$ErrorActionPreference="Stop"
$Server=Read-Host "URL do painel (Enter para padrão)";if(-not $Server){$Server="https://animacao2d.vps11710.panel.icontainer.work"}
$Token=Read-Host "Token ANIMA_OPENTOONZ_TOKEN";if(-not $Token){throw "Token obrigatório."}
$Composer="$env:ProgramFiles\OpenToonz\tcomposer.exe";if(-not(Test-Path $Composer)){$Composer=Read-Host "Caminho completo do tcomposer.exe"};if(-not(Test-Path $Composer)){throw "tcomposer.exe não encontrado."}
$Python=Get-Command python -ErrorAction SilentlyContinue;if(-not $Python){throw "Python 3 não encontrado."}
$env:ANIMA_OPENTOONZ_SERVER=$Server.TrimEnd("/");$env:ANIMA_OPENTOONZ_TOKEN=$Token;$env:ANIMA_TCOMPOSER=$Composer
Write-Host "Agente OpenToonz iniciado. Mantenha a janela aberta." -ForegroundColor Cyan
& $Python.Source (Join-Path $PSScriptRoot "opentoonz-worker.py")
