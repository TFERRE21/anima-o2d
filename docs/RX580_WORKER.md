# Estação local RX 580 — ComfyUI

O motor de produção de episódios é o Cartoon 2D no servidor. O worker Blender/RX580 foi desativado e não participa mais da fila de episódios.

## Uso da RX 580

A placa pode ser aproveitada no computador Windows para geração de imagens e elementos visuais pelo ComfyUI. O agente disponível em `tools/windows-gpu-agent` conversa com a API `/api/comfy` e exige que o ComfyUI esteja instalado e iniciado localmente.

Configure na VPS:
- `ANIMA_COMFY_TOKEN`: segredo aleatório compartilhado com o agente local.

No Windows, configure a URL HTTPS do painel e o mesmo token no agente ComfyUI. Mantenha o ComfyUI acessível apenas em localhost; o agente faz as conexões de saída para a VPS.

## Limite atual de integração

A geração ComfyUI é um serviço auxiliar de criação de imagens. Ela ainda não substitui nem acelera o desenho de cada quadro do renderizador Cartoon 2D. A renderização de quadros permanece no servidor, e o encoder usa H.264 por software. A aceleração AMD AMF só deve ser ativada quando uma instalação local do FFmpeg confirmar suporte a `h264_amf`.

Não inicie `iniciar-worker.ps1`: esse é o agente legado de Blender 3D e não é utilizado pelo motor atual.
