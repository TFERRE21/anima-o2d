# Anima 2D Studio — Pequenos Guardiões

Estúdio web para produção de episódios infantis 2D com Luna, Tomi e Pipo.

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
- O roteiro tem 12 cenas de storyboard, falas próprias de Luna, Tomi e Pipo, narração do narrador e uma sequência curta construída a partir do clímax da história.
- A criação do roteiro é uma etapa explícita anterior à renderização: `POST /api/stories/generate`; a prévia fica em `GET /api/jobs/{id}/story`; a animação começa em `POST /api/jobs/{id}/render`.
- A agenda automática faz a mesma sequência internamente: grava a história completa e depois dispara a renderização.

| Formato | Resolução | Duração exigida |
|---|---:|---:|
| Episódio 16:9 | 1920×1080 | Entre 5 e 10 minutos (301–600 s) |
| Shorts 9:16 | 1080×1920 | Entre 1:00 e 1:30 |

O renderizador mede a duração da faixa de áudio final e ajusta a velocidade dentro de limites para respeitar as duas faixas. O episódio longo alterna narrador e falas dos três personagens. O Shorts usa a pista, a virada e a solução da missão — a parte mais impactante — com áudio e seleção de cenas próprios. Se não conseguir cumprir a faixa, marca o job como falha em vez de entregar um vídeo com duração incorreta.

## Motor de animação atual

- Personagens 2D desenhados proceduralmente com Pillow, mantendo figurinos, emblemas e proporções consistentes entre cenas.
- Cenários cinematográficos diferentes por planeta e por cena: espaço, chegada, vilas, jardins, montanhas, desertos, pistas, reunião, ação, surpresa e celebração, usando bioma e objeto da missão.
- Personagens maiores e mais expressivos, com poses de caminhada, descoberta, surpresa, apontar, conversa, trabalho e comemoração.
- Movimento contínuo de braços, pernas, corpo, cauda, foguete, partículas, flores, água e efeitos de luz, com renderização intermediária a 8 fps e saída final a 24 fps.
- Boca animada no personagem correspondente ao trecho de fala. Ainda não é sincronização labial por fonema.
- Vídeo final efetivamente redimensionado em alta qualidade para 1920×1080 e 1080×1920.
- Sem caixas de legenda, título ou texto explicativo sobreposto ao quadro: as falas são transmitidas pelo áudio.
- Vozes em português brasileiro: no ICP, Edge TTS alterna `pt-BR-ThalitaMultilingualNeural` (narrador), `pt-BR-FranciscaNeural` (Luna) e `pt-BR-AntonioNeural` (Tomi); Pipo usa a mesma base de Antonio com pitch elevado. O mapa fixo fica salvo em `/data/jobs/voice-profiles.json`, junto aos dados persistentes, para manter a identidade vocal entre episódios. Requer conexão de saída à internet. Em ambientes com espeak-ng, o motor usa variações de pitch para diferenciar as falas.
- FFmpeg: usa a instalação do sistema quando disponível; no runtime Python do ICP, usa o binário portátil fornecido por `imageio-ffmpeg`.
- A duração é medida com ffprobe quando disponível, Mutagen e leitura de metadados pelo FFmpeg portátil como alternativas.
- Renderização MP4 com FFmpeg.
- Saídas 16:9 (1920×1080) e 9:16 (1080×1920).
- Jobs em segundo plano e histórico persistido em volume Docker.

> Este é um motor 2D procedural em evolução, não uma ferramenta de animação profissional nem geração de vídeo por IA. As poses e o movimento da boca são guiados pela linha do tempo das falas, mas ainda não existe sincronização labial por fonema, rigging com ossos ou animação desenhada quadro a quadro por artista.

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

Painel: http://localhost:8000  
API: http://localhost:8000/docs  
Saúde: http://localhost:8000/api/health

Vídeos, histórico e preferências ficam persistidos em `./data`.

## Publicar no iContainer (Standalone Python)

O projeto pode rodar no módulo Standalone com runtime Python, sem selecionar Node.js. O repositório contém `app.py` na raiz e `requirements.txt` para o instalador do painel.

- Runtime: Python 3.13 (ou versão compatível).
- Instalação: `pip install -r requirements.txt` (executado pelo build do painel).
- Comando de inicialização: `python app.py`.
- Porta: `5000` por padrão; o processo respeita a variável de ambiente `PORT` quando fornecida.
- Volume persistente recomendado: montar em `/data/jobs` para preservar vídeos, roteiros, configurações e o token OAuth do YouTube durante novos deploys.
- A renderização usa `imageio-ffmpeg` e `edge-tts` como alternativas portáveis. Edge TTS precisa que o servidor consiga acessar o serviço externo de voz.

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
