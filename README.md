# Anima 2D

Plataforma para criar vídeos animados 2D e preparar publicações no YouTube em dois formatos:

- **16:9** — 1920×1080 (vídeo horizontal)
- **9:16** — 1080×1920 (Shorts vertical)

## Série original: Pequenos Guardiões — A Liga do Bem

Duas crianças e seu cão companheiro ajudam a comunidade, resolvem mistérios e ensinam valores por meio de aventuras sem violência gráfica.

- **Luna:** inventora corajosa, curiosa e empática.
- **Tomi:** estrategista leal, calmo e justo.
- **Pipo:** cão caramelo brincalhão e atento.

Valores: respeito, honestidade, amizade, empatia, responsabilidade, cidadania, segurança e cuidado com os animais e o meio ambiente.

### Documentação criativa
- [Bíblia da série e personagens](docs/biblia-da-serie.md)
- [Episódio 01 — O Mistério das Mochilas](docs/episodio-01-o-misterio-das-mochilas.md)
- [Pipeline de animação e exportação dupla](docs/pipeline-de-animacao.md)

## Escopo da plataforma

- Cadastro de projetos e histórias.
- Roteiro dividido em cenas.
- Personagens e identidade visual consistentes.
- Geração de imagens/cenas por provedor configurável.
- Narração em português, música e legendas.
- Renderização e composição com FFmpeg.
- Pré-visualização e exportação MP4.
- Publicação no YouTube via OAuth e YouTube Data API, com opção de agendamento.
- Painel de jobs, status, erros e histórico.

## Arquitetura inicial

- Backend: Python + FastAPI.
- Renderização: FFmpeg.
- Frontend: HTML/CSS/JavaScript inicial (sem dependência de build).
- Execução: Docker Compose.

## Desenvolvimento local

```bash
docker compose up --build
```

API: http://localhost:8000  
Documentação: http://localhost:8000/docs

## Configuração

Copie `.env.example` para `.env` e configure as credenciais do provedor de geração e do YouTube. Nunca coloque chaves reais no Git.

## Estado do projeto

A estrutura inicial da aplicação, painel básico e documentos criativos estão versionados. A geração real de cenas, rigging/animação, sincronização labial, fila de renderização e integração OAuth ainda precisam ser implementadas e testadas. A publicação automática permanece desativada até configuração e autorização explícitas.
