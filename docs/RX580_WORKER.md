# RX 580 Windows render worker

## Architecture

The Windows computer initiates outbound HTTPS requests to the Anima API (pull worker).
No inbound Windows port, router forwarding, or public Windows service is required.
The VPS keeps the existing CPU renderer as the fallback. Remote rendering is opt-in.

## VPS environment

Set these environment variables in the VPS/container deployment settings:

- ANIMA_REMOTE_WORKER_ENABLED=true
- ANIMA_WORKER_TOKEN=<a long random secret>
- ANIMA_WORKER_API_URL=http://127.0.0.1:5000

Generate a token on a trusted machine with:

    python -c "import secrets; print(secrets.token_urlsafe(48))"

Use the same token on the VPS and Windows worker. Never commit it to Git or paste it into issues/logs.
Restart/redeploy the VPS after setting the variables. If the token is absent, remote rendering is rejected.

## Windows automatic startup (no login required)

Prerequisites:
- Windows 10/11.
- Blender 5.2 installed.
- Python 3.10 or newer installed for all-users, with a stable executable path.
- The repository extracted to a permanent local folder (not a temporary Downloads extraction).

Open Windows PowerShell as Administrator in tools\windows-gpu-agent and run:

    Set-ExecutionPolicy -Scope Process Bypass -Force
    .\instalar-worker-servico.ps1

Enter the public HTTPS panel URL and the VPS worker token when prompted. The installer:
- Stores the token encrypted with Windows DPAPI (machine scope).
- Restricts the configuration folder to SYSTEM and local Administrators.
- Registers a Windows Task Scheduler task triggered at system startup, running as SYSTEM with highest privileges.
- Starts the worker immediately; no interactive Windows login is required.
- Writes output to %ProgramData%\AnimaStudio3D\RX580Worker\worker.log.

Check status (PowerShell as Administrator):

    Get-ScheduledTask -TaskName "AnimaStudio3D-RX580-Worker"
    Get-ScheduledTaskInfo -TaskName "AnimaStudio3D-RX580-Worker"
    Get-Content "$env:ProgramData\AnimaStudio3D\RX580Worker\worker.log" -Tail 50

The PC must remain powered on, connected to the internet, and awake. The task restarts after failure and retries network connections through the worker loop.

Remove the automatic worker:

    .\remover-worker-servico.ps1

## Manual mode

For interactive troubleshooting only, run iniciar-worker.ps1 from PowerShell. Do not run manual and scheduled workers simultaneously; they use the same worker identity.

The worker uses Blender's Eevee engine and the scene script shipped with this repository. It sends PNG frames back to the VPS as a ZIP; FFmpeg/audio/video assembly remains on the VPS.

## API checks

Authenticated worker status:

    GET /api/worker/status
    Authorization: Bearer <token>

A connected worker should appear in workers. The worker must remain running while a job is rendered.

## Safety and rollback

- The worker API requires a shared bearer token.
- Windows initiates outbound connections only; do not open inbound firewall/router ports.
- Keep the token private and rotate it if exposed.
- To return to VPS CPU rendering, set ANIMA_REMOTE_WORKER_ENABLED=false and redeploy.
- Do not enable remote mode until the worker is running and the token matches on both sides.
- This first implementation keeps task state in the API process memory; run a single API replica/worker process for this setup. A VPS restart interrupts in-flight remote jobs, which can be retried from the panel.
