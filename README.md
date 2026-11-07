# Anima 2D — Pequenos Guardiões

Estúdio para criar episódios infantis 2D com Luna, Tomi e Pipo, exportando versões horizontais e verticais.

## O que já funciona nesta primeira versão

- Painel web conectado à API.
- Geração de um episódio de demonstração com personagens 2D desenhados por código (Pillow).
- Movimentos simples de balanço, braços e detalhes animados ao longo das cenas.
- Roteiro informado no painel usado nas legendas e na narração sintetizada com espeak-ng em português.
- Renderização MP4 com FFmpeg.
- Exportação em **16:9 (1920×1080)** e **9:16 (1080×1920)**.
- Jobs em segundo plano, barra de progresso, histórico persistido e links para baixar os arquivos.
- Docker Compose com volume persistente em `./data`.

> Esta é uma base funcional de animação procedural 2D, não um gerador de vídeo por IA nem uma produção de estúdio completa. O desenho atual usa personagens vetoriais simples, cenas predefinidas e voz sintética básica. Rigging avançado, sincronização labial, trilha licenciada, geração de arte por IA e publicação OAuth no YouTube ainda precisam ser integrados e testados.

## Série original

**Pequenos Guardiões — A Liga do Bem**

- Luna: inventora corajosa.
- Tomi: estrategista leal.
- Pipo: cão companheiro.

A série ensina respeito, honestidade, amizade, empatia, responsabilidade, cidadania e segurança. Os protagonistas resolvem conflitos com diálogo, raciocínio e ajuda de adultos, sem violência gráfica.

### Documentos criativos
- [Bíblia da série e personagens](docs/biblia-da-serie.md)
- [Episódio 01 — O Mistério das Mochilas](docs/episodio-01-o-misterio-das-mochilas.md)
- [Pipeline de animação e exportação dupla](docs/pipeline-de-animacao.md)

## Executar com Docker

```bash
cp .env.example .env
docker compose up --build -d
```

Painel: http://localhost:8000  
API: http://localhost:8000/docs  
Saúde: http://localhost:8000/api/health

Os vídeos e metadados ficam em `./data` no host.

## Executar sem Docker

Instale FFmpeg, espeak-ng e fontes DejaVu; depois:

```bash
pip install -r backend/requirements.txt
ANIMA_STORAGE=./data uvicorn backend.app.main:app --app-dir . --host 0.0.0.0 --port 8000
```

## API principal

- `GET /api/health` — saúde do serviço.
- `GET /api/config` — formatos e dependências detectadas.
- `POST /api/generate` — cria job de renderização.
- `GET /api/jobs` — histórico.
- `GET /api/jobs/{id}` — progresso e arquivos.
- `GET /api/jobs/{id}/download/{fmt}` — baixa MP4 (`16:9` ou `9:16`).

## Próximas integrações

1. Melhorar os modelos dos personagens e criar rigs 2D reutilizáveis.
2. Adicionar TTS neural com vozes consistentes e trilha sonora licenciada.
3. Implementar storyboard e geração de cenários/arte assistida por IA.
4. Adicionar OAuth do YouTube, upload, miniaturas e agendamento após autorização do dono do canal.
5. Criar testes visuais e de áudio para cada renderização.

Nunca coloque tokens ou chaves reais no Git. Revise o vídeo e os direitos de todos os recursos antes de publicar, especialmente por se tratar de conteúdo infantil.
