# Anima 2D

Plataforma para criar vídeos animados 2D e preparar publicações no YouTube em dois formatos:

- **16:9** — 1920×1080 (vídeo horizontal)
- **9:16** — 1080×1920 (Shorts vertical)

## Escopo

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

## Importante

O projeto inicial oferece a estrutura da aplicação e endpoints de saúde/configuração. A geração real de imagens/vídeos depende de um provedor de IA configurado; a publicação depende da autorização OAuth do canal. Não há publicação automática ativada por padrão.
