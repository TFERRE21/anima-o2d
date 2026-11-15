<#
.SYNOPSIS
  Instala/inspeciona um ComfyUI DirectML isolado para Radeon RX 580 no Windows.
.DESCRIPTION
  Preserva integralmente C:\ComfyUI-Zluda, HIP, ZLUDA, modelos e venv originais.
  Requer Python 3.11, Git e internet. Instala pacotes APENAS em venv-directml.
  DirectML e uma rota alternativa, nao garantia de geracao.
#>
param(
    [ValidateSet("verificar", "instalar", "iniciar")]
    [string]$Modo = "verificar",
    [string]$PastaDirectML = "C:\AnimaStudio\ComfyUI-DirectML",
    [string]$PastaModelos = "C:\ComfyUI-Zluda\ComfyUI-Zluda"
)

$ErrorActionPreference = "Stop"
$root = [System.IO.Path]::GetFullPath($PastaDirectML)
$venvPython = Join-Path $root "venv-directml\Scripts\python.exe"
$launcher = Join-Path $root "comfyui.bat"
$constraints = Join-Path $root "anima-directml-constraints.txt"
$modelsYaml = Join-Path $root "anima-modelos.yaml"
$models = Join-Path $PastaModelos "models\checkpoints"

if (-not (Test-Path -LiteralPath $models -PathType Container)) {
    throw "Nao encontrei os checkpoints existentes em $models. Nenhum arquivo foi modificado."
}

Write-Host "=== ANIMA STUDIO / DIRECTML / AMD RX 580 ==="
Write-Host "ComfyUI alternativo: $root"
Write-Host "Checkpoints preservados: $models"

if ($Modo -eq "verificar") {
    Write-Host "Git:" ([bool](Get-Command git -ErrorAction SilentlyContinue))
    Write-Host "Python Launcher:" ([bool](Get-Command py -ErrorAction SilentlyContinue))
    Write-Host "ComfyUI DirectML:" (Test-Path -LiteralPath (Join-Path $root "main.py"))
    Write-Host "Ambiente DirectML:" (Test-Path -LiteralPath $venvPython)
    Write-Host "Modelos existentes:" @((Get-ChildItem -LiteralPath $models -Filter *.safetensors -File)).Count
    Write-Host "Nenhuma instalacao realizada."
    exit 0
}

if ($Modo -eq "instalar") {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw "Git nao encontrado no PATH. Instale o Git for Windows primeiro."
    }
    if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
        throw "Python Launcher (py) nao encontrado no PATH."
    }
    & py -3.11 --version
    if ($LASTEXITCODE -ne 0) {
        throw "Python 3.11 nao encontrado. Este perfil nao usa Python 3.15."
    }
    if (-not (Test-Path -LiteralPath $root)) {
        New-Item -ItemType Directory -Path (Split-Path -Parent $root) -Force | Out-Null
        Write-Host "Clonando ComfyUI v0.3.10 isolado em $root"
        & git clone --depth 1 --branch v0.3.10 https://github.com/Comfy-Org/ComfyUI.git $root
        if ($LASTEXITCODE -ne 0) { throw "Falha no clone do ComfyUI." }
    }
    if (-not (Test-Path -LiteralPath (Join-Path $root ".git")) -or
        -not (Test-Path -LiteralPath (Join-Path $root "main.py"))) {
        throw "A pasta DirectML existe mas nao tem um clone valido do ComfyUI. Nao vou sobrescrever."
    }
    if (-not (Test-Path -LiteralPath $venvPython)) {
        Write-Host "Criando ambiente independente do ZLUDA..."
        & py -3.11 -m venv (Join-Path $root "venv-directml")
        if ($LASTEXITCODE -ne 0) { throw "Falha ao criar venv-directml." }
    }
    & $venvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "Falha ao atualizar pip no venv DirectML." }

    # torch-directml 0.2.5 targets the torch 2.4.1 generation; the 2025
    # ComfyUI release is pinned to avoid newer torch dependencies.
    @'
torch==2.4.1
torchvision==0.19.1
torchaudio==2.4.1
torch-directml==0.2.5.dev240914
transformers==4.44.2
numpy==1.26.4
'@ | Set-Content -LiteralPath $constraints -Encoding ASCII

    & $venvPython -m pip install "torch-directml==0.2.5.dev240914" "torchaudio==2.4.1" "transformers==4.44.2" "numpy==1.26.4"
    if ($LASTEXITCODE -ne 0) { throw "Falha na instalacao do DirectML no venv isolado." }
    & $venvPython -m pip install -r (Join-Path $root "requirements.txt") -c $constraints
    if ($LASTEXITCODE -ne 0) { throw "Falha nas dependencias do ComfyUI antigo." }
    & $venvPython -m pip check
    if ($LASTEXITCODE -ne 0) { throw "Dependencias incompativeis no DirectML. Nao alterei o ZLUDA." }

    # Reuse checkpoint directory; no copies and no admin-only symlinks.
    $base = $PastaModelos.Replace("\", "/")
    $yamlContent = "anima_zluda_models:\n  base_path: $base\n  checkpoints: models/checkpoints\n  vae: models/vae\n  loras: models/loras\n"
    $yamlContent = $yamlContent.Replace("\n", [Environment]::NewLine)
    Set-Content -LiteralPath $modelsYaml -Value $yamlContent -Encoding ASCII

    @'
@echo off
cd /d "%~dp0"
"%~dp0venv-directml\Scripts\python.exe" main.py --directml --cpu-vae --listen 127.0.0.1 --port 8188 --extra-model-paths-config "%~dp0anima-modelos.yaml" --disable-auto-launch
echo ComfyUI DirectML foi encerrado. Confira as mensagens acima.
pause
'@ | Set-Content -LiteralPath $launcher -Encoding ASCII

    Write-Host "Validando dispositivo DirectML..."
    & $venvPython -c "import torch, torch_directml; d=torch_directml.device(); print('DirectML:',torch_directml.device_name(-1)); a=torch.tensor([1.0]).to(d); print('Operacao DirectML:',(a+1).cpu().tolist())"
    if ($LASTEXITCODE -ne 0) {
        throw "DirectML instalado, mas dispositivo nao executou operacao basica. Veja driver AMD."
    }
    Write-Host "DirectML instalado separadamente. ZLUDA original preservado."
}

if (-not (Test-Path -LiteralPath $launcher)) {
    throw "ComfyUI DirectML nao instalado. Execute -Modo instalar primeiro."
}
if ($Modo -eq "iniciar") {
    $busy = @(Get-NetTCPConnection -LocalPort 8188 -State Listen -ErrorAction SilentlyContinue)
    if ($busy.Count -gt 0) {
        Write-Host "A porta 8188 ja esta ocupada. Nao vou abrir segunda instancia."
        $busy | Select-Object LocalAddress, LocalPort, OwningProcess | Format-Table
        throw "Encerre apenas a instancia ComfyUI/ZLUDA atual antes de iniciar DirectML."
    }
    & $launcher
} else {
    Write-Host "Para iniciar: .\instalar-directml-rx580.ps1 -Modo iniciar"
    Write-Host "Para conectar o agente: defina COMFYUI_INSTALL_DIR=$root e inicie iniciar-comfyui-agent.ps1"
}
