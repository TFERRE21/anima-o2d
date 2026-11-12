# Estação local RX 580 — ComfyUI e aceleração de mídia

## Architecture

O computador Windows pode executar o ComfyUI localmente para gerar elementos visuais com a Radeon RX 580. Ele inicia conexões de saída; não é necessário abrir portas de entrada nem configurar redirecionamento no roteador. A renderização dos episódios 2D permanece no servidor e não depende do Blender.

## VPS environment

Set these environment variables in the VPS/container deployment settings:

- `ANIMA_REMOTE_WORKER_ENABLED=true`
- `ANIMA_WORKER_TOKEN=<a long random secret>`
- `ANIMA_WORKER_API_URL=http://127.0.0.1:5000`

Generate a token on a trusted machine with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Use the same token on the VPS and Windows worker. Never commit it to Git or paste it into issues/logs.
Restart/redeploy the VPS after setting the variables. If the token is absent, remote rendering is rejected.

## Windows worker

1. Download and extract the latest `gpu-rx580-experimental` branch ZIP.
2. Keep the folder on the Windows PC with Blender 5.2 installed.
3. Open PowerShell in `tools\windows-gpu-agent`.
4. Run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force
.\iniciar-worker.ps1
```

5. Enter the public HTTPS panel URL and the same secret token configured on the VPS.
6. Leave the PowerShell window open. The worker sends heartbeats and waits for render jobs.

O agente ComfyUI é um serviço opcional de criação de ativos visuais, não o renderizador de episódios. Não inicie o worker Blender legado para produção 2D. Para codificação AMD, use FFmpeg local que liste `h264_amf` em `ffmpeg -encoders`; caso contrário, a codificação H.264 por software continua disponível.

## API checks

Authenticated worker status:

```
GET /api/worker/status
Authorization: Bearer <token>
```

A connected worker should appear in `workers`. The worker must remain running while a job is rendered.

## Safety and rollback

- The worker API requires a shared bearer token.
- Windows initiates outbound connections only; do not open inbound firewall/router ports.
- Keep the token private and rotate it if exposed.
- To return to VPS CPU rendering, set `ANIMA_REMOTE_WORKER_ENABLED=false` and redeploy.
- Do not enable remote mode until the worker is running and the token matches on both sides.
- This first implementation keeps task state in the API process memory; run a single API replica/worker process for this setup. A VPS restart interrupts in-flight remote jobs, which can be retried from the panel.
