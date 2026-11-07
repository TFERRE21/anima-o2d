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

## Motor de animação atual

- Personagens 2D desenhados proceduralmente com Pillow, com visual aprimorado, figurinos, emblemas e detalhes faciais.
- Movimentos simples por quadro e cenários ilustrados.
- Narração sintetizada com espeak-ng em português, quando disponível.
- Renderização MP4 com FFmpeg.
- Saídas 16:9 (1920×1080) e 9:16 (1080×1920).
- Jobs em segundo plano e histórico persistido em volume Docker.

> Este é um MVP funcional de animação procedural, não uma ferramenta de animação profissional nem geração de vídeo por IA. Ainda faltam rigging avançado, sincronização labial, vozes neurais consistentes, trilha licenciada e geração dinâmica de cenários por IA.

## Automação e publicação — estado real

O painel salva preferências de formatos, revisão obrigatória e rotina editorial sugerida. A fila de episódios, renderização e atualização de status são automáticas após iniciar uma geração.

**A integração de upload e agendamento via YouTube Data API foi adicionada ao backend.** É necessário configurar `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET` e `YOUTUBE_REDIRECT_URI`, autorizar o canal no painel e aprovar editorialmente cada episódio. O painel permite enviar cada formato e agendar a publicação pelo YouTube. A automação recorrente que cria roteiros sozinha, publica em calendário sem ação humana, miniaturas e métricas analíticas ainda não foi concluída.

## Série original

**Pequenos Guardiões — A Liga do Bem**
- Luna: inventora corajosa.
- Tomi: estrategista leal.
- Pipo: cão companheiro.

A série ensina honestidade, amizade, empatia, responsabilidade, cidadania e segurança. Os protagonistas resolvem conflitos com diálogo, raciocínio e ajuda de adultos, sem violência gráfica.

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

## Endpoints

- `GET /api/health`
- `GET /api/config`
- `GET /api/dashboard`
- `GET /api/youtube/status`
- `GET /api/youtube/connect` (inicia OAuth)
- `GET /api/youtube/callback` (retorno OAuth)
- `POST /api/jobs/{id}/publish` (upload ou agendamento após aprovação)
- `GET/PUT /api/studio-settings`
- `POST /api/generate`
- `GET /api/jobs`
- `GET /api/jobs/{id}`
- `POST /api/jobs/{id}/review`
- `GET /api/jobs/{id}/download/{fmt}`

## Segurança antes de publicar em VPS

O MVP ainda não tem autenticação de usuário. Não o exponha publicamente sem colocar autenticação, HTTPS, proteção de endpoints e limites de uso. Nunca envie chaves OAuth ou o arquivo `youtube-token.json` para o Git. Configure credenciais em secrets do ambiente. Cadastre a URL de callback no Google Cloud Console. O OAuth deve ser testado em domínio HTTPS real antes de uso público.
