param(
    [string]$BlenderPath = "",
    [int]$Frames = 60,
    [int]$Samples = 8
)

$ErrorActionPreference = "Stop"
$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$SceneScript = Join-Path $RepoRoot "backend\app\blender_scene.py"
$Reports = Join-Path $PSScriptRoot "..\reports"
$FramesDir = Join-Path $Reports "rx580-real-scene-frames"
$ConfigPath = Join-Path $Reports "rx580-real-scene-config.json"
$ResultPath = Join-Path $Reports "rx580-real-scene-result.json"

if (-not (Test-Path $SceneScript)) {
    throw "Arquivo do motor real nao encontrado: $SceneScript. Extraia o ZIP completo da branch experimental."
}
if ($Frames -lt 12 -or $Frames -gt 240) {
    throw "Frames deve ficar entre 12 e 240 para este benchmark inicial."
}
New-Item -ItemType Directory -Force -Path $Reports | Out-Null
if (Test-Path $FramesDir) { Remove-Item $FramesDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $FramesDir | Out-Null

if (-not $BlenderPath) {
    $cmd = Get-Command blender.exe -ErrorAction SilentlyContinue
    if ($cmd) { $BlenderPath = $cmd.Source }
}
if (-not $BlenderPath) {
    $candidate = "$env:ProgramFiles\Blender Foundation\Blender 5.2\blender.exe"
    if (Test-Path $candidate) { $BlenderPath = $candidate }
}
if (-not $BlenderPath -or -not (Test-Path $BlenderPath)) {
    throw "Blender nao encontrado. Informe -BlenderPath com o caminho completo."
}

$sceneDefs = @(
    @{ title="A NOVA MISSAO"; caption="Os pequenos guardioes chegam ao novo planeta."; visual_action="A equipe chega em uma aventura."; action="walk" },
    @{ title="EXPLORANDO"; caption="Luna e Tomi observam o lugar."; visual_action="Os amigos exploram o ambiente."; action="explore" },
    @{ title="NOVOS AMIGOS"; caption="A equipe encontra habitantes do planeta."; visual_action="Os amigos conversam com os habitantes."; action="converse" },
    @{ title="A DESCOBERTA"; caption="Uma pista aparece no caminho."; visual_action="Luna descobre uma pista importante."; action="discover" },
    @{ title="A SOLUCAO"; caption="Todos trabalham juntos."; visual_action="A equipe resolve o desafio em conjunto."; action="work" }
)
$sourceIndices = @(0,1,2,3,4)
$config = @{
    format = "9:16"
    resolution = @(360,640)
    fps = 12
    total_frames = $Frames
    frames_dir = $FramesDir
    scenes = $sceneDefs
    scene_source_indices = $sourceIndices
    story_plan = @{
        planet = "Aurora-7"
        biome = "Floresta luminosa"
        mission_object = "Cristal de energia"
        landmark = "Arvore central"
        inhabitants = "Moradores amigaveis"
        palette = "azul, verde e dourado"
    }
    voice_timeline = @()
}
$configJson = $config | ConvertTo-Json -Depth 8
[System.IO.File]::WriteAllText($ConfigPath, $configJson, (New-Object System.Text.UTF8Encoding($false)))

$env:ANIMA_EEVEE_SAMPLES = "$Samples"
$env:ANIMA_RENDER_SCALE = "100"
$env:ANIMA_BLENDER_THREADS = "6"

Write-Host "=== ANIMA STUDIO 3D | CENA REAL + RX 580 ===" -ForegroundColor Cyan
Write-Host "Blender: $BlenderPath"
Write-Host "Quadros: $Frames | Resolucao: 360x640 | Samples: $Samples | Engine: Eevee"
Write-Host "GPU detectada no teste anterior: AMD Radeon RX 580 2048SP"
Write-Host "Este teste usa o arquivo blender_scene.py real do projeto."
Write-Host ""

$BlenderLog = Join-Path $Reports "rx580-real-scene-blender.log"
$timer = [System.Diagnostics.Stopwatch]::StartNew()

# Windows PowerShell 5.1 can turn Blender's harmless stderr warnings into
# terminating NativeCommandError records when ErrorActionPreference is Stop.
# Keep the native process output visible and logged, but let Blender finish;
# the real success/failure decision is made from its exit code and frame count.
$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    & $BlenderPath --background --factory-startup --python-exit-code 1 --python $SceneScript -- --config $ConfigPath 2>&1 |
        Tee-Object -FilePath $BlenderLog
    $code = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
    $timer.Stop()
}

$pngCount = @(Get-ChildItem -Path $FramesDir -Filter "frame-*.png" -ErrorAction SilentlyContinue).Count
$timing = $null
$stageTimings = @()
if (Test-Path $BlenderLog) {
    foreach ($line in Get-Content $BlenderLog) {
        if ($line -match 'ANIMA_RENDER_TIMING:(\{.*\})') {
            try { $timing = $Matches[1] | ConvertFrom-Json } catch { $timing = $null }
        }
        if ($line -match 'ANIMA_STAGE_TIMING:(\{.*\})') {
            try { $stageTimings += ($Matches[1] | ConvertFrom-Json) } catch { }
        }
    }
}
$secondsPerFrame = if ($timing -and $timing.seconds_per_frame) {
    [math]::Round([double]$timing.seconds_per_frame, 4)
} else { $null }
$setupSeconds = if ($timing) { [math]::Round([double]$timing.setup_seconds, 2) } else { $null }
$renderSeconds = if ($timing) { [math]::Round([double]$timing.render_seconds, 2) } else { $null }
# Extrapolate only frame-render time; scene setup is paid once per output video.
$estimate771 = if ($secondsPerFrame -and $setupSeconds -ne $null) {
    [math]::Round(($setupSeconds + ($secondsPerFrame * 771)) / 60, 1)
} else { $null }

$result = [ordered]@{
    status = if ($code -eq 0 -and $pngCount -eq $Frames) { "ok" } else { "error" }
    gpu = "AMD Radeon RX 580 2048SP"
    blender = & $BlenderPath --version | Select-Object -First 1
    frames_requested = $Frames
    frames_rendered = $pngCount
    resolution = "360x640"
    samples = $Samples
    total_seconds = [math]::Round($timer.Elapsed.TotalSeconds, 2)
    setup_seconds = $setupSeconds
    render_seconds = $renderSeconds
    seconds_per_frame_render_only = $secondsPerFrame
    estimated_minutes_for_771_frames_plus_one_setup = $estimate771
    stage_timings = $stageTimings
    exit_code = $code
    frames_directory = $FramesDir
    blender_log = $BlenderLog
}
$result | ConvertTo-Json -Depth 5 | Set-Content -Path $ResultPath -Encoding UTF8
Write-Host ""
$result | Format-List
Write-Host "Relatorio salvo em: $ResultPath" -ForegroundColor Green
if ($code -ne 0) { throw "O Blender retornou codigo $code." }
if ($pngCount -ne $Frames) { throw "Foram gerados $pngCount de $Frames quadros." }
