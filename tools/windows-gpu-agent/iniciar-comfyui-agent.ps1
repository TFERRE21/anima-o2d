$ErrorActionPreference="Stop"
$env:ANIMA_STUDIO_URL=Read-Host "URL do Anima Studio (ex.: https://animacao2d.vps11710.panel.icontainer.work)"
$env:ANIMA_COMFY_TOKEN=Read-Host "Token ANIMA_COMFY_TOKEN configurado na VPS"
if(-not $env:ANIMA_STUDIO_URL -or -not $env:ANIMA_COMFY_TOKEN){throw "URL e token sao obrigatorios."}
$env:COMFYUI_URL="http://127.0.0.1:8188"
$python="C:\ComfyUI-Zluda\ComfyUI-Zluda\venv\Scripts\python.exe"
$agent=Join-Path $PSScriptRoot "comfyui-agent.py"
if(-not(Test-Path $python)){throw "Python do agente nao encontrado: $python"}

# If an independent DirectML installation exists, use it by default.
# The local Python running the agent remains the original tested ZLUDA venv:
# no Torch or ZLUDA packages are changed on the host.
$directmlRoot="C:\AnimaStudio\ComfyUI-DirectML"
$directmlPython=Join-Path $directmlRoot "venv-directml\Scripts\python.exe"
$directmlLauncher=Join-Path $directmlRoot "comfyui.bat"
$requested=($env:ANIMA_GPU_BACKEND+"").Trim().ToLowerInvariant()
if(-not $requested){
    $requested=if((Test-Path $directmlPython) -and (Test-Path $directmlLauncher)){
        "directml"
    }else{
        "zluda"
    }
}
if($requested -eq "directml"){
    if(-not((Test-Path $directmlPython) -and (Test-Path $directmlLauncher))){
        throw "DirectML nao instalado. Execute instalar-directml-rx580.ps1 -Modo instalar."
    }
    $env:COMFYUI_INSTALL_DIR=$directmlRoot
    Write-Host "Motor selecionado: DirectML / AMD RX 580 (instalacao independente)."
}elseif($requested -eq "zluda"){
    $env:COMFYUI_INSTALL_DIR="C:\ComfyUI-Zluda\ComfyUI-Zluda"
    Write-Host "Motor selecionado: ZLUDA / AMD RX 580."
}else{
    throw "ANIMA_GPU_BACKEND deve ser 'directml' ou 'zluda'."
}
$env:ANIMA_GPU_BACKEND=$requested
& $python -m pip show requests Pillow | Out-Null
if($LASTEXITCODE -ne 0){
    throw "Dependencias requests/Pillow ausentes no Python do agente; verifique venv."
}
& $python $agent
