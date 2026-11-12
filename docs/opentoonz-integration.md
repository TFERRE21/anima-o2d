# OpenToonz — render remoto

O agente Windows executa `tcomposer.exe` em batch para renderizar uma cena OpenToonz existente (`.tnz`) em PNG e enviar os quadros em ZIP à VPS.

Requisitos: OpenToonz instalado, Python 3 no PATH e cena/arquivos vinculados acessíveis no computador. Configure o secret `ANIMA_OPENTOONZ_TOKEN` na VPS (ou use `ANIMA_WORKER_TOKEN`).

Iniciar em `tools\windows-gpu-agent`:
`powershell -ExecutionPolicy Bypass -File .\iniciar-opentoonz-worker.ps1`

API protegida por Bearer: `GET /api/opentoonz/worker/status`, `POST /api/opentoonz/tasks` (config com `scene_path`, `frame_start`, `frame_end`), `GET /api/opentoonz/tasks/{id}`.

**Limite:** esta etapa renderiza cenas .tnz existentes; ainda não transforma roteiro em desenhos, rigs, exposições e timeline. A geração integral de episódios pelo formulário do painel depende do construtor automático de cenas e do pacote de assets. Não marcar OpenToonz como motor padrão antes dessa etapa e de um teste real.
