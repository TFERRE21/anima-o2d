# Migração do Anima Studio para Docker no ICP

## Situação

O serviço atual foi criado como Standalone Python. Esse runtime não tem Blender e responde
`503` em `POST /api/jobs/{id}/render`. O projeto agora exige Blender para renderização,
sem fallback silencioso para vídeo 2D.

O repositório `TFERRE21/anima-o2d`, branch `main`, contém um `Dockerfile` que instala Blender,
Xvfb, Mesa, FFmpeg e espeak-ng. O `docker-compose.yml` constrói esse Dockerfile e persiste os
arquivos em `/data/jobs`.

## Implantação sem derrubar o Standalone

1. No ICP, abrir **Container → Repositório** e conectar `TFERRE21/anima-o2d), branch `main`.
2. Abrir **Container → Compose** e criar um projeto usando o `docker-compose.yml` da raiz.
3. Na primeira subida, manter a publicação externa em `5001` (padrão deste Compose), com a
   porta interna `5000`. Assim é possível testar o novo serviço sem disputar a porta/URL do
   Standalone antigo.
4. Confirmar que o volume persistente do serviço está montado em `/data/jobs`.

## Atenção aos dados

O Compose usa um volume Docker nomeado `anima2d_data`. Esse volume é novo e não contém
automaticamente os dados do Standalone antigo. Antes da troca definitiva, preservar ou copiar
o conteúdo do diretório que o Standalone usa para `ANIMA_STORAGE` (padrão `/data/jobs`) para
o volume que será montado em `/data/jobs` no Compose. Não excluir nem recriar o volume antigo
antes de confirmar os arquivos e perfis de voz.

## Verificação antes do corte

1. Abrir `/api/health` no endereço temporário do serviço novo.
2. Confirmar `blender: true`, `render_engine: "blender"` e `generation_enabled: true`.
3. Conferir que o Compose aparece saudável no ICP.
4. Criar uma história de teste e renderizar um episódio curto de validação.
5. Confirmar no log a presença do Blender e a criação do MP4 3D.

Somente depois desses passos, alterar o domínio/rota para o novo serviço e publicar a porta
externa definitiva. Manter o Standalone antigo disponível até validar o novo serviço.

## Variáveis e portas

- `ANIMA_RENDER_ENGINE=blender`
- `BLENDER_BIN=blender`
- `ANIMA_STORAGE=/data/jobs`
- Porta interna: `5000`
- Porta externa de teste: `5001` (pode ser substituída por `HOST_PORT`)
- Volume persistente: `/data/jobs`

## Limite operacional

A conexão desta sessão permite atualizar e validar o repositório GitHub, mas não controla a
sessão autenticada do painel ICP. Portanto, a criação do projeto Compose, a associação do
volume antigo e a alteração da rota/domínio precisam ser confirmadas no painel ICP.
