$ErrorActionPreference="Stop"
$env:ANIMA_STUDIO_URL=Read-Host "URL do Anima Studio (ex.: https://animacao2d.vps11710.panel.icontainer.work)"
$env:ANIMA_COMFY_TOKEN=Read-Host "Token ANIMA_COMFY_TOKEN configurado na VPS"
if(-not $env:ANIMA_STUDIO_URL -or -not $env:ANIMA_COMFY_TOKEN){throw "URL e token são obrigatórios."}
$env:COMFYUI_URL="http://127.0.0.1:8188"
$python="C:\ComfyUI-Zluda\ComfyUI-Zluda\venv\Scripts\python.exe"
$agent=Join-Path $PSScriptRoot "comfyui-agent.py"
if(-not(Test-Path $python)){throw "Python do ComfyUI não encontrado: $python"}
& $python -m pip install requests
& $python $agent
