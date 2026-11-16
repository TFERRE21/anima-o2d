# ANIMA STUDIO — Histórias Desenhadas em 2D

Estúdio infantil **2D com narradora**, sem GPU, ComfyUI, Runway, APIs de imagem ou Blender. O projeto reaproveita a biblioteca original de ilustrações 2D dos Pequenos Guardiões (Luna, Tomi e Pipo), produzidas por código e mantidas visualmente estáveis entre os episódios.

## Experiência no painel

1. Clique em **Criar história original** (tema opcional).
2. Confira o roteiro e o storyboard da aventura em um novo planeta.
3. Clique em **Aprovar roteiro e produzir vídeo 2D** uma vez.
4. O servidor cria a voz da **narradora** e monta as ilustrações de cada cena.
5. Cada ilustração começa como papel vazio, recebe os traços de lápis, ganha cor progressivamente e é exibida enquanto a narradora conta aquela parte da história.
6. O painel mantém o progresso, a **prévia visual ao vivo** e os downloads finais.
7. A revisão e a publicação no YouTube continuam separadas.

O motor não tenta produzir vídeos 3D, nem fica aguardando GPU ou o ComfyUI. Episódios antigos com roteiro aprovado e bloqueados por `CUDA out of memory` podem ser retomados automaticamente ao atualizar a aplicação sem apagar o armazenamento.

## Tecnologia e qualidade

- Ilustrações: `backend/app/cartoon2d.py` (arte 2D original da série: personagens consistentes, cenários de planetas e acessórios);
- Desenho progressivo: `backend/app/narrated_draw_2d.py` (extração de contornos, papel de desenho, lápis e revelação em duas etapas);
- Narração: `espeak-ng` voz feminina brasileira (`pt-br+f3`), incluída na VPS. É uma voz sintética local; pode soar robótica. O projeto também contém integração Edge TTS, mas a produção 2D padrão não depende de serviço de voz em nuvem;
- Montagem: FFmpeg, libx264, formatos **1920×1080** e **1080×1920**;
- Durações: episódio 16:9 de **5 a 10 minutos**, Shorts 9:16 entre **1:00 e 1:30**;
- Infraestrutura: CPU e RAM da VPS, sem GPU externa, assinatura de imagem ou APIs pagas.

**Limitação artística:** o motor mostra um desenho previamente criado surgindo progressivamente por contorno e cor. Não gera uma nova ilustração complexa por inteligência artificial a partir de cada frase nem faz animação quadro a quadro de personagens articulados. O resultado é uma história ilustrada 2D, não um filme cinematográfico gerado por difusão.

## Implantação no iContainer

No GitHub: `TFERRE21/anima-o2d`, branch `main`.

Faça atualização/rebuild da aplicação `animacao2d`, preservando **obrigatoriamente** o volume persistente `/data/jobs`, que mantém roteiros, episódios e vídeos.

Para Docker:

```bash
docker compose up -d --build
```

Variáveis principais:

```env
ANIMA_STORAGE=/data/jobs
ANIMA_RENDER_ENGINE=2d
ANIMA_DRAW_FPS=8
ANIMA_AUTO_INSTALL_BLENDER=0
```

Não precisa configurar `ANIMA_IMAGE_PROVIDER`, `RUNWAYML_API_SECRET`, `OPENAI_API_KEY`, `ANIMA_COMFY_TOKEN`, nem instalar/ligar ComfyUI. Se as chaves antigas existirem no iContainer, o novo pipeline não as usa; por segurança, pode removê-las mais tarde.

**Verificações:**
- `GET /api/health`: `render_engine=narrated-draw-2d`, `gpu_required=false`.
- `GET /api/health/2d`: FFmpeg e voz local disponíveis.
- `GET /api/diagnostics`: detalhes da capacidade de mídia.
- `GET /api/jobs/{id}/art/board`: status da produção 2D, sem fila de imagens.
- `GET /api/jobs/{id}/render-status`: progresso e prévia de ilustração.
- `GET /api/jobs/{id}/download/16:9` e `/9:16`: download dos vídeos.

O projeto mantém alguns módulos antigos do Blender e ComfyUI para histórico/compatibilidade de APIs, mas o caminho ativo de produção 2D não os executa.

## Testes

```bash
python -m unittest discover -s backend/tests -v
```

O CI do GitHub valida o motor 2D, a renderização real de um trecho de lápis/cor via FFmpeg e a construção da imagem Docker.

## Segurança

Não coloque credenciais do YouTube nem tokens no Git. Mantenha o controle de revisão antes de publicar vídeos. O painel usa histórias fictícias e material próprio para as ilustrações; conteúdos enviados à plataforma devem ser revisados.
