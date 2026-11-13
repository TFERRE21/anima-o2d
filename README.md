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


## Implantação no iContainer (imagem Python genérica)

O iContainer pode iniciar a aplicação usando uma imagem `python:3.13.0` em vez de construir o `Dockerfile` do repositório. Nesse caso, instalar Blender via `docker exec` é temporário: uma recriação do container desfaz os pacotes instalados.

O Anima Studio detecta automaticamente a ausência do Blender na inicialização da API. Se estiver dentro de Docker, com usuário root e `apt-get`, instala Blender, Xvfb, FFmpeg e espeak-ng **em segundo plano, apenas nesse container**, sem bloquear a API. A instalação é repetida quando uma imagem genérica é recriada. O progresso e eventuais falhas aparecem em `GET /api/diagnostics`, no campo `blender_bootstrap`, e nos logs prefixados por `[cartoon3d-blender]`. Enquanto a instalação estiver em andamento, a produção continua indisponível, sem retornar para 2D.

Desative a recuperação automática com `ANIMA_AUTO_INSTALL_BLENDER=0`. A solução definitiva e mais rápida continua sendo configurar o iContainer para **construir e usar a imagem do Dockerfile**, que já contém o Blender pronto. Não remova o volume de episódios existente ao migrar a aplicação.

## Evolução do motor artístico: ilustração por IA + animação

O motor atual Blender ainda cria modelos geométricos. A nova arquitetura separa **direção de arte** de **movimento**. `backend/app/art_director.py` já gera, para cada história, instruções de arte com referências oficiais e identidade travada de Luna, Tomi e Pipo. Consulte `GET /api/jobs/{job_id}/art-plan` depois de gerar um roteiro.

A criação das imagens finais precisa de um gerador conectado (por exemplo, o agente ComfyUI da estação RX 580, descrito em `docs/integracao-comfyui.md`) e revisão visual. Essas imagens **ainda não são usadas automaticamente pelo renderizador de episódios**: nesta etapa implementamos a direção de arte, não um sistema completo de corte em camadas e rig. A qualidade e a identidade dos personagens precisam ser aprovadas antes da integração definitiva ao Blender. Uma imagem plana serve para parallax/câmera, mas não oferece movimentos realistas de braços, boca e pernas sem camadas, poses ou uma malha/rig próprio.

### Blender 3.4 / falha nativa
Se ocorrer `Segmentation fault` logo após `ANIMA_ART_VERSION`, há suspeita de incompatibilidade do Blender/OpenGL no container. Uma consulta nativa a `gpu.platform.renderer_get()` foi removida do processo em segundo plano, e a limpeza da cena não depende mais de operadores de seleção. Essa mudança reduz pontos de risco **mas não garante eliminar** outras falhas do Blender. Verifique `/tmp/blender.crash.txt` no container, os eventos `ANIMA_BOOT` e se a aplicação utiliza uma imagem Docker compatível com GPU/OpenGL.

O acesso ao ChatGPT Plus não inclui créditos de API ou acesso automático à execução de modelos de geração de imagens na VPS.

## Diagnóstico e desempenho do Cartoon 3D no iContainer

A renderização pode demorar muito com Eevee sem GPU. O motor detecta OpenGL por software (`llvmpipe`) e usa **Blender Workbench com materiais, luz de estúdio e geometria 3D real** quando `ANIMA_3D_RENDER_MODE=auto`. Workbench é um estilo de renderização 3D mais leve, visualmente diferente do Eevee; não é o antigo motor 2D. Para forçar a iluminação Eevee, configure `ANIMA_3D_RENDER_MODE=eevee` e providencie GPU/OpenGL compatíveis.

- `ANIMA_CARTOON_CAPTURE_FPS=12`: gera doze poses 3D distintas por segundo e codifica o vídeo final a 24 fps (repetição de quadros). Aumentar para 24 melhora a fluidez, mas exige o dobro dos quadros. A qualidade espacial das imagens não muda com a taxa de poses.
- `ANIMA_EARLY_PREVIEW=1`: renderiza uma primeira imagem 3D reduzida assim que a cena estiver montada e disponibiliza na prévia ao vivo.
- `ANIMA_FIRST_FRAME_TIMEOUT=360`: encerra uma tentativa que não consegue produzir sequer o primeiro quadro dentro de seis minutos, com erro explicativo; `ANIMA_BLENDER_TOTAL_TIMEOUT` controla o limite total.
- `GET /api/jobs/{id}/render-status`: retorna o estado da renderização, total de quadros disponíveis, indicação de prévia pronta e últimas mensagens técnicas.
- Arquivos `render-log-9x16.txt` ou `render-log-16x9.txt` ficam no diretório persistente do episódio, facilitando o diagnóstico sem depender do fluxo de acessos HTTP do painel.

A produção continua exclusivamente em Cartoon 3D. Este modo de recuperação prioriza conseguir renderizar na VPS, **não substitui uma GPU dedicada nem garante renderização de episódios completos em poucos minutos**. Alterações no GitHub só se aplicam à aplicação quando o iContainer recebe o novo código e reinicia seu container.

## Segurança
Antes de expor o painel publicamente, configure autenticação, HTTPS, proteção dos endpoints e limites de uso. Nunca envie credenciais OAuth ou youtube-token.json para o Git.