# Anima Studio 3D — Pequenos Guardiões

Estúdio web para produção de episódios infantis em 3D com Luna, Tomi, Pipo e moradores de planetas originais.

## Painel do estúdio

O painel possui:
- Visão geral com indicadores de episódios criados, em produção, finalizados e aguardando revisão.
- Biblioteca de episódios com status, formatos e downloads.
- Criação de episódios e acompanhamento da renderização em tempo real.
- Aprovação editorial de episódios finalizados.
- Preferências de produção e rotina editorial.
- Área de acompanhamento da integração com YouTube.

## Motor de histórias e durações

- Cada episódio recebe um identificador de planeta não repetido, com bioma, habitantes, problema e solução próprios.
- O motor escolhe uma missão e valor educativo diferentes, preservando Luna, Tomi e Pipo.
- O roteiro tem 15 cenas de storyboard, falas próprias de Luna, Tomi e Pipo, narração do narrador e uma sequência curta construída a partir do clímax da história.
- A criação do roteiro é uma etapa explícita anterior à renderização: `POST /api/stories/generate`; a prévia fica em `GET /api/jobs/{id}/story`; a animação começa em `POST /api/jobs/{id}/render`.
- A agenda automática faz a mesma sequência internamente: grava a história completa e depois dispara a renderização.

| Formato | Resolução | Duração exigida |
|---|---:|---:|
| Episódio 16:9 | 1920×1080 | Entre 5 e 10 minutos (301–600 s) |
| Shorts 9:16 | 1080×1920 | Entre 1:00 e 1:30 |

O renderizador mede a duração da faixa de áudio final e ajusta a velocidade dentro de limites para respeitar as duas faixas. O episódio longo alterna narrador e falas dos três personagens. O Shorts usa a pista, a virada e a solução da missão — a parte mais impactante — com áudio e seleção de cenas próprios. Se não conseguir cumprir a faixa, marca o job como falha em vez de entregar um vídeo com duração incorreta.

## Motor de animação 3D

- Renderizador baseado em **Blender 3D**, com geometria real, câmera com perspectiva ortográfica e profundidade, iluminação de estúdio, sombras, cavidade e contornos suaves.
- Luna, Tomi e Pipo são modelos 3D procedurais com volumes arredondados, figurinos, acessórios e articulações próprias; moradores também aparecem nos encontros. A direção visual é uma série infantil original de aventura, colorida e cinematográfica, sem reproduzir personagens, logotipo ou modelos de outra franquia.
- Animação por cena: caminhada com ciclos de braços/pernas, exploração com deslocamento, apontar, gestos, surpresa, conversa virada entre os personagens, trabalho em equipe e comemoração.
- Linha do tempo de voz por personagem: a boca do falante é animada durante a fala, incluindo moradores locais. As vozes ficam fixas em `/data/jobs/voice-profiles.json`.
- Planetas têm cenários 3D diferentes conforme bioma e missão: florestas, oceanos, gelo, desertos, ilhas flutuantes, vilas, pontes, faróis, bibliotecas, equipamentos e objetos da história.
- Câmera acompanha a ação e muda o enquadramento em cada parte do storyboard. Não são usadas caixas de legenda ou títulos sobre a imagem.
- Blender Eevee é usado como renderizador 3D estilizado, com materiais, luzes suaves, sombras e profundidade; Workbench é fallback de compatibilidade. A saída final é codificada em 24 fps e em 1920×1080 ou 1080×1920.
- Cada parágrafo da narradora está ligado à cena correspondente por marcação de tempo real do áudio; o vídeo troca de cena junto com a fala. Atores fazem a ação descrita (pouso, exploração, investigação, descoberta, conversa com moradores, trabalho em equipe, diário e retorno). Durante diálogos, a câmera favorece quem fala, o personagem falante gesticula e os demais reagem como ouvintes. A boca é animada conforme os intervalos das falas; ainda não é sincronização fonema a fonema nem rig facial profissional.

### Runtime necessário

**A renderização de vídeo requer runtime Docker.** O modo Python Standalone não contém Blender e não deve ser usado para renderizar. O Dockerfile instala Blender, Xvfb e Mesa para renderização 3D sem monitor/GPU dedicada.

- Engine: `ANIMA_RENDER_ENGINE=blender`.
- Binário: `BLENDER_BIN=blender`.
- Porta interna do app: `5000` (`PORT=5000`). O Compose publica essa porta em `${HOST_PORT:-5000}`; use `HOST_PORT=5001` para testar sem conflitar com o Standalone antigo.
- Volume persistente: `/data/jobs` para roteiros, perfis de voz, vídeos e tokens.
- O endpoint de saúde informa se Blender está disponível; sem o motor 3D, a API bloqueia a renderização com mensagem explícita em vez de entregar um vídeo 2D como substituto.

## Automação e publicação — estado real

O painel salva preferências de formatos, revisão obrigatória e rotina editorial sugerida. O motor sempre escreve e salva a história antes de iniciar qualquer renderização. Na criação manual, o roteiro e o storyboard são apresentados para revisão; a animação só começa após aprovação. No calendário automático, o roteiro é criado primeiro e depois segue para renderização em segundo plano.

**A integração de upload e agendamento via YouTube Data API foi adicionada ao backend.** É necessário configurar `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET` e `YOUTUBE_REDIRECT_URI`, autorizar o canal no painel e aprovar editorialmente cada episódio. O painel permite enviar cada formato e agendar a publicação pelo YouTube. A produção recorrente de roteiros e vídeos pode ser ativada no calendário do estúdio. A publicação automática sem revisão ainda não está habilitada; o upload e o agendamento no YouTube exigem autorização do canal e aprovação editorial.

## Série original

**Pequenos Guardiões — A Liga do Bem**
- Luna: inventora corajosa.
- Tomi: estrategista leal.
- Pipo: cão companheiro.

A série ensina honestidade, amizade, empatia, responsabilidade, cidadania e segurança. **Todos os episódios levam Luna, Tomi e Pipo a um planeta diferente**, onde conhecem os habitantes e ajudam a resolver um desafio com diálogo, raciocínio e cooperação, sem violência gráfica. O gerador mantém um catálogo de mundos e cria novos identificadores para não repetir destinos.

Documentos criativos:
- [Bíblia da série](docs/biblia-da-serie.md)
- [Episódio 01 — O Mistério das Mochilas](docs/episodio-01-o-misterio-das-mochilas.md)
- [Pipeline de animação](docs/pipeline-de-animacao.md)

## Executar com Docker

```bash
cp .env.example .env
docker compose up -d --build
```

Painel: http://localhost:5000  
API: http://localhost:5000/docs  
Saúde: http://localhost:5000/api/health

Vídeos, histórico e preferências ficam persistidos em `./data`.

## Publicar no iContainer (runtime Docker)

Para renderização 3D, publique a imagem Docker construída a partir do Dockerfile. Não selecione runtime Node.js nem Python Standalone para produção de vídeos 3D.

- Build: `docker build -t anima-studio-3d .`.
- Inicialização: o Dockerfile inicia Uvicorn e Blender no modo headless via Xvfb/Mesa.
- Porta interna: `5000` (defina `PORT` para outro valor se o painel exigir).
- Variável: `ANIMA_RENDER_ENGINE=blender`.
- Volume persistente: montar em `/data/jobs` para preservar vídeos, roteiros, vozes e token OAuth do YouTube.
- Voz neural: Edge TTS exige conexão de saída à internet.

## Endpoints

- `GET /api/health`
- `GET /api/config`
- `GET /api/dashboard`
- `GET /api/youtube/status`
- `GET /api/youtube/connect` (inicia OAuth)
- `GET /api/youtube/callback` (retorno OAuth)
- `POST /api/jobs/{id}/publish` (upload ou agendamento após aprovação)
- `GET/PUT /api/studio-settings`
- `POST /api/stories/generate` (cria a história antes do vídeo)
- `GET /api/jobs/{id}/story` (prévia do roteiro)
- `POST /api/jobs/{id}/render` (renderiza após aprovação)
- `POST /api/generate` (compatibilidade; também cria roteiro primeiro)
- `GET /api/jobs`
- `GET /api/jobs/{id}`
- `POST /api/jobs/{id}/review`
- `GET /api/jobs/{id}/download/{fmt}`

## Segurança antes de publicar em VPS

O MVP ainda não tem autenticação de usuário. Não o exponha publicamente sem colocar autenticação, HTTPS, proteção de endpoints e limites de uso. Nunca envie chaves OAuth ou o arquivo `youtube-token.json` para o Git. Configure credenciais em secrets do ambiente. Cadastre a URL de callback no Google Cloud Console. O OAuth deve ser testado em domínio HTTPS real antes de uso público.
