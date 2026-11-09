# RX 580 Windows render worker

## Architecture

The Windows computer initiates outbound HTTPS requests to the Anima API (pull worker).
No inbound Windows port, router forwarding, or public Windows service is required.
The VPS keeps the existing CPU renderer as the fallback. Remote rendering is opt-in.

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

The worker uses Blender's Eevee engine and the scene script shipped with this repository. It sends PNG frames back to the VPS as a ZIP; FFmpeg/audio/video assembly remains on the VPS.

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
