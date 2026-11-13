# Anima Studio Cartoon 3D — Pequenos Guardiões

Estúdio web para produção de histórias infantis em animação tridimensional Cartoon, com personagens recorrentes, cenários 3D, câmera cinematográfica, movimentos e vozes.

## Painel
O painel mantém criação e revisão de roteiros, biblioteca de episódios, progresso da renderização em tempo real, prévia ao vivo, histórico, configurações e integração com YouTube.

## Motor exclusivo Cartoon 3D
- O único motor autorizado para novos episódios é o Blender 3D com Eevee.
- O renderizador 2D anterior está desativado nas rotas de prévia e não é chamado pelo pipeline de produção.
- Luna e Tomi são personagens tridimensionais originais, com cabeça, rosto, cabelo, roupas, braços e pernas articulados.
- Pipo é um companheiro canino tridimensional com corpo, focinho, orelhas, patas, colete e cauda.
- Os cenários são montados como ambientes 3D por bioma e missão, com objetos, vegetação, construções, iluminação e câmeras.
- As cenas são animadas por quadros-chave e ações; a fala continua sincronizada por linha do tempo de áudio e movimentos de boca.
- Blender gera quadros PNG; FFmpeg compõe o vídeo e sincroniza o áudio.

## Formatos
| Formato | Saída | Duração |
|---|---:|---:|
| YouTube | 1920×1080 | 5 a 10 minutos |
| Shorts | 1080×1920 | 60 a 90 segundos |

## Runtime de produção
Python 3.12, Blender (executável em modo background), Eevee, Xvfb, FFmpeg, Edge TTS ou espeak-ng. O Dockerfile instala o Blender e valida o executável durante o build.
- Porta interna: 5000.
- Volume persistente: /data/jobs.
- Healthcheck: GET /api/health/3d.
- Diagnóstico: GET /api/diagnostics.
- Catálogo: GET /api/engines/catalog.
- A rota antiga /api/health/2d e as rotas /api/2d/preview retornam 410 Gone.

## Renderização e hardware
O pipeline atual executa Blender no servidor, em modo background, usando Eevee. A renderização pode ser limitada pela CPU e pela disponibilidade de OpenGL no container. A Radeon RX 580 local não é considerada conectada automaticamente: para utilizá-la como worker remoto será necessário configurar e validar um agente de renderização seguro na máquina que possui a GPU. Não afirmar aceleração por GPU sem comprovação no runtime.

## Histórias e publicação
O roteiro é criado antes da renderização e passa por revisão editorial. As falas mantêm perfis de voz estáveis. O upload/agendamento no YouTube requer OAuth configurado e aprovação editorial.

## Executar com Docker
```bash
docker compose up -d --build
```

Painel: http://localhost:5000  
API: http://localhost:5000/docs  
Saúde: http://localhost:5000/api/health/3d

## Segurança
Antes de expor o painel publicamente, configure autenticação, HTTPS, proteção dos endpoints e limites de uso. Nunca envie credenciais OAuth ou youtube-token.json para o Git.