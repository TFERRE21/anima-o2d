# ANIMA STUDIO — Histórias Desenhadas em 2D

Estúdio infantil **2D com narradora**, sem GPU, ComfyUI, Runway, APIs de imagem ou Blender. O projeto reaproveita a biblioteca original de ilustrações 2D dos Pequenos Guardiões (Luna, Tomi e Pipo), produzidas por código e mantidas visualmente estáveis entre os episódios.

## Experiência no painel

1. Clique em **Criar história original** (tema opcional).
2. Confira o roteiro e o storyboard da aventura em um novo planeta.
3. Clique em **Aprovar roteiro e produzir vídeo 2D** uma vez.
4. O servidor cria a voz da **narradora** e monta as ilustrações de cada cena.
5. Cada quadrinho começa vazio, ganha contornos e depois cores. Os anteriores permanecem na página enquanto a narradora conta a cena seguinte.
6. O painel mantém o progresso, a **prévia visual ao vivo** e os downloads finais.
7. A revisão e a publicação no YouTube continuam separadas.

O motor não tenta produzir vídeos 3D, nem fica aguardando GPU ou o ComfyUI. Episódios antigos com roteiro aprovado e bloqueados por `CUDA out of memory` podem ser retomados automaticamente ao atualizar a aplicação sem apagar o armazenamento.

## Quadrinhos profissionais — referência visual aprovada

O vídeo de referência aprovado mostra página de quadrinhos infantis com
contornos uniformes, personagens consistentes, cenas completas e **mão real**
segurando caneta. O motor anterior usava uma ilustração simples esticada
para o vídeo, efeito de metade lápis/metade cor e um lápis voador. Essa
montagem foi substituída por:

- **Gibi quadro a quadro:** até 3 painéis empilhados no Shorts e 4 no
  horizontal. A narradora revela o próximo painel; os quadros anteriores
  permanecem desenhados na página.
- **Resolução interna maior:** 720×1280 vertical ou 1280×720 horizontal,
  finalizados em 1080×1920 ou 1920×1080. O vídeo não deve ser anunciado como
  ilustração Full HD nativa quando o material de entrada é menor.
- **Sem lápis flutuando:** somente aparece uma mão *fotográfica real*
  recortada quando o usuário disponibiliza um PNG com transparência.
- **Biblioteca editorial por episódio:** sempre prefere imagens profissionais
  de cada cena em vez do fallback 2D procedural.

### Como adicionar a mão real uma única vez

Obtenha/produza uma fotografia **autorizada** de mão humana real segurando
uma caneta, com fundo transparente (PNG RGBA, mínimo 150px).
Salve em um local persistente da VPS, por exemplo
\`/data/jobs/series/hand-real.png\`, e adicione a variável:

\`\`\`env
ANIMA_REAL_HAND_PNG=/data/jobs/series/hand-real.png
\`\`\`

Sem esse arquivo, a renderização continua **sem mão e sem lápis voador**.
Não afirmamos que uma mão real foi filmada se apenas uma ilustração existe.

### Opção preferida: filmagem real da mão desenhando

Para uma mão humana **realmente em movimento**, grave uma mão segurando
caneta com fundo verde uniforme, em MP4 (pode ser reutilizado em todos os
episódios). Salve por exemplo em `/data/jobs/series/hand-real.mp4` e
configure na VPS:

```env
ANIMA_REAL_HAND_VIDEO=/data/jobs/series/hand-real.mp4
```

O FFmpeg remove o fundo verde pelo filtro `colorkey` e sobrepõe a
filmagem na posição do quadrinho ativo, sem precisar de GPU. A mão
continua sendo uma filmagem pré-gravada e seu movimento **não acompanha
necessariamente cada contorno da imagem com precisão manual**. Isso
é mais autêntico que uma foto recortada, mas não é idêntico a desenhar
quadro por quadro à mão sobre papel verdadeiro. Quando configurado,
o vídeo tem preferência sobre `ANIMA_REAL_HAND_PNG`.

### Para ter a arte idêntica à referência aprovada

Para cada história, o motor procura imagens originais de cada cena em:

\`\`\`text
/data/jobs/<id-do-episodio>/comic-art/scene-00.png
/data/jobs/<id-do-episodio>/comic-art/scene-01.png
...
\`\`\`

Aceita PNG, WebP ou JPG. Essas artes devem ter sido **criadas ou licenciadas**
para uso no vídeo e revisadas na qualidade editorial desejada. Recomenda-se
1280×720 ou superior, personagens e identidade visual consistentes, e
cenários diferentes conforme a história. A referência publicada no chat
não gera automaticamente todos os quadros de episódios futuros.

Se as imagens não existirem, a aplicação usa as antigas ilustrações
\`cartoon2d.py\`, que são simples e **não atingem o acabamento da
referência**. Para bloquear vídeos de qualidade insuficiente, ative:

\`\`\`env
ANIMA_COMIC_REQUIRE_CURATED_ART=1
\`\`\`

Nesse modo o processamento informa qual arquivo de arte falta em vez
de publicar um vídeo visualmente inferior. Esta restrição exige que
um ilustrador ou outro gerador forneça as artes antes da renderização.
Sem GPU e sem APIs de imagens, é inviável garantir novas ilustrações
de qualidade profissional e exclusivas para qualquer roteiro apenas
com Pillow/FFmpeg. FFmpeg anima arte; não substitui um desenhista.


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
