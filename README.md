## Identidade do canal e automação YouTube (2026-11-17)

**Canal:** Luna, Tomi e Pipo — Pequenos Guardiões.

A partir da renderização final, `backend/app/channel_branding.py` adiciona:

- **16:9:** vinheta animada original de 4 segundos com marca, desenho da
  própria história, música infantil criada localmente e protagonistas;
  encerramento de 5 segundos convidando a se inscrever e acompanhar a série.
- **9:16 Shorts:** encerramento vertical de 5 segundos, sem a abertura longa.
- Música original e artes da história: não usa áudios ou personagens
  licenciados de terceiros. Mantém os vídeos originais e as falas narradas.

`backend/app/youtube_package.py` gera automaticamente para cada formato:
título até 100 caracteres, sinopse derivada do roteiro aprovado, planeta,
aprendizado, descrição, hashtags relevantes, palavras-chave e miniatura JPG.
Os arquivos ficam em `/data/jobs/<job_id>/youtube-ready/<16x9|9x16>/`.

`backend/app/youtube_publisher.py` envia via Google OAuth usando o fluxo
`videos.insert` resumable; configura
`status.selfDeclaredMadeForKids=true`, categoria Film & Animation, e
tenta inserir miniatura via `thumbnails.set`. O YouTube pode restringir
uploads de projetos de API não verificados a **privados**. Só o YouTube
Studio pode confirmar a publicação e o processamento da mídia.

### Ativar automação — sem publicar nada antes do consentimento

1. No ambiente da VPS, configure `YOUTUBE_CLIENT_ID`,
   `YOUTUBE_CLIENT_SECRET` e `YOUTUBE_REDIRECT_URI` com a URL HTTPS
   pública correta, usando a tela de consentimento OAuth e YouTube Data API v3
   no Google Cloud. **Nunca comite tokens/segredos no GitHub.**
2. Abra o painel **YouTube & postagens** e clique em **Conectar canal**.
   Autorize o canal do YouTube na conta Google escolhida.
3. Na **Central de automação**, habilite **Produção automática** e
   **Publicação automática**, escolha dias e horários (Brasília) e salve.
4. Se **Exigir revisão** estiver ligado, o upload aguarda aprovação editorial
   de cada episódio. Para o fluxo inteiramente automático, desative a revisão
   e confirme o aviso. Os envios continuam limitados a **novos episódios
   concluídos após a ativação**, nunca publicando antigos sem querer.

A fila persistente do servidor verifica horários de minuto em minuto e agenda
um slot para o 16:9, com o Shorts 15 minutos depois. O progresso dos uploads,
os IDs de vídeo, links, metadados e tentativas são preservados no `job.json`
para sobreviver a reinicializações. Uma falha de upload depois de iniciada
bloqueia novas tentativas do mesmo formato até conferência manual, evitando
publicações duplicadas.

**Nota sobre canais infantis:** vídeos marcados para crianças não oferecem
notificações pelo sininho, comentários ou telas finais interativas como os
vídeos comuns. O convite integrado no vídeo diz “Inscreva-se no canal e
acompanhe nossas próximas histórias”, sem prometer ativar sininho.
Essa opção não muda a classificação infantil verdadeira do vídeo.

A geração visual e a fila foram implementadas, porém uma publicação real
precisa ser validada com o OAuth já conectado, e a montagem completa
FFmpeg precisa ser testada na VPS.


# ANIMA STUDIO — Histórias Desenhadas em 2D

## Correção do visual dos personagens — v12

Com as credenciais Cloudflare configuradas, o Anima Studio usa agora o
modo `reference_ai` por padrão, salvo quando
`ANIMA_CHARACTER_MODE=fixed` estiver explicitamente definido na VPS.
Esse modo usa o FLUX.2 Klein 4B e a prancha incorporada para ilustrar
protagonistas, habitantes e cenário juntos; não cola os personagens antigos
por cima da arte. Reaplica composição 16:9 (1024×576), evitando recortes
verticais que aumentavam as pessoas e escondiam as cidades. O prompt limita
a escala dos personagens conforme cidade, panorama e conversa.

Os balões exibem apenas diálogos diretos: resumos de narração nos Shorts
como “Na parte mais difícil da missão...” não são mais tratados como
falas de Luna ou Tomi. Balões verdadeiros continuam sincronizados com
o texto falado. Os novos arquivos estão em
`story-comic-reference-v12-<cache_tag>`, evitando imagens antigas em cache.

**Atenção:** o modo de referência gera imagens pela Cloudflare e consome
sua franquia de Workers AI. Para retornar ao modo simples basta definir
`ANIMA_CHARACTER_MODE=fixed`, mas a qualidade antiga volta. A identidade
dos personagens é guiada por referência, não matematicamente garantida.
Uma renderização real na VPS é necessária para validar qualidade e escala.

## Elenco com referência visual por IA — v11 (opcional)

O caminho de maior fidelidade agora pode gerar a **cena completa** pela IA,
incluindo Luna, Tomi, Pipo, habitantes e ambiente. Não cola sprites sobre
a arte. A imagem de referência de 480×480 é montada automaticamente usando
os desenhos fixos já incorporados ao repositório; não há ZIP ou upload manual.
O texto da cena controla escala, enquadramento, expressões, casas, vegetação,
identidade do planeta e quando os habitantes locais devem aparecer.
A narração e os balões reais continuam sendo acrescentados pelo renderizador.

O FLUX.1 Schnell aceita só texto; portanto, esta modalidade exige o
**FLUX.2 Klein 4B**, que recebe referência em
`input_image_0` via `multipart/form-data`. Configure no ambiente da VPS:

```env
ANIMA_CHARACTER_MODE=reference_ai
ANIMA_CHARACTER_IMAGE_MODEL=@cf/black-forest-labs/flux-2-klein-4b
CLOUDFLARE_API_TOKEN=token_ja_configurado
CLOUDFLARE_ACCOUNT_ID=account_id_ja_configurado
ANIMA_REQUIRE_ILLUSTRATED_SCENES=1
```

A variável `CLOUDFLARE_AI_MODEL` pode permanecer no Schnell: o modo de
referência usa `ANIMA_CHARACTER_IMAGE_MODEL` separadamente. Para retornar
à composição anterior, use `ANIMA_CHARACTER_MODE=fixed` (padrão).
Os conjuntos de imagens usam `story-comic-reference-v11-<cache_tag>`, sem
reutilizar cenas antigas. A troca para `reference_ai` é **intencionalmente
manual**, pois gera novas chamadas à API e pode consumir créditos/cobrança.
O plano Free permite até sua franquia, depois bloqueia operações em vez de
garantir imagens ilimitadas. Consulte o consumo da conta Cloudflare.

**Limitações:** a referência ajuda a manter os personagens, mas não garante
identidade 100% idêntica entre cenas. O modelo pode modificar detalhes ou
ignorar composição; o servidor não possui validação visual automática.
Nenhuma renderização final deste modo foi confirmada na VPS.
Os balões de fala do roteiro permanecem fora da geração por IA.

## Balões com as falas reais e cenários Cloudflare — v10

O arquivo `backend/app/dialogue_timeline.py` usa as linhas do roteiro
aprovado e os intervalos do áudio montado. Balões mostram **somente
palavras realmente previstas para Luna, Tomi, Pipo e moradores**.
A narração descritiva continua sem balão; nenhum “UAU!” ou “VAMOS!”
genérico é inventado. Falas compridas são divididas em balões de até
oito palavras, sem substituir o texto, e cada segmento recebe um intervalo
proporcional à duração real do trecho de voz. Durante o mesmo quadrinho, a
fala visível muda com o trecho narrado, sem redesenhar tudo. Os quadros
concluídos preservam a última fala da cena. As expressões do elenco foram
corrigidas para evitar a boca circular “0” desenhada por cima dos rostos.

A API da **Cloudflare Workers AI/FLUX.1 Schnell** também é compatível com
o gerador de fundos ilustrados. Para ativá-la no contêiner da VPS:

```env
CLOUDFLARE_API_TOKEN=seu_token_secreto
CLOUDFLARE_ACCOUNT_ID=seu_account_id
CLOUDFLARE_AI_MODEL=@cf/black-forest-labs/flux-1-schnell
CLOUDFLARE_AI_STEPS=4
ANIMA_REQUIRE_ILLUSTRATED_SCENES=1
```

Não envie o token para o GitHub, não coloque a chave no JavaScript do
navegador e não compartilhe a credencial em capturas de tela.
O sistema detecta Cloudflare automaticamente quando Account ID e token
estão presentes (a menos que `ANIMA_SCENE_IMAGE_PROVIDER=openai` seja
explicitamente configurado). Com a Cloudflare ativa, os fundos se baseiam
no planeta, vegetação, vilas, personagens locais e ação narrada. O resultado
da API tem cache, mas **a franquia gratuita não é ilimitada** e a qualidade
exata da imagem de referência não é garantida pelo modelo FLUX Schnell.

O motor registra o conjunto ilustrado em
`story-comic-dialogue-v10-<cache_tag>`, ou no fallback local
`story-comic-dialogue-local-v10`, evitando reaproveitar balões antigos.
O render produz pequenos trechos MP4 sincronizados aos segmentos da
narração e os concatena em cada cena. Testes estão em
`tests/test_dialogue_timeline.py`; execução integral no servidor ainda
precisa ser confirmada.

## Motor de cenários ilustrados v9 — qualidade de livro infantil

O mecanismo simples de Pillow continua disponível apenas como alternativa
local. Para criar paisagens ricas como as referências, o renderizador agora
gera **uma ilustração completa por cena** com GPT Image e depois sobrepõe
os personagens fixos Luna, Tomi e Pipo. Casas, vegetação, cidades, nativos,
céu e detalhes seguem o planeta e cada trecho narrado. Um planeta mantém
seu bioma e identidade visual; cenas usam ângulos e ações diferentes.

**Ativação única no ambiente do contêiner da VPS** (nunca no repositório):

```env
ANIMA_SCENE_IMAGE_API_KEY=chave_da_api_de_imagens
ANIMA_SCENE_IMAGE_MODEL=gpt-image-2.5-flare
ANIMA_SCENE_IMAGE_QUALITY=medium
ANIMA_REQUIRE_ILLUSTRATED_SCENES=1
```

Também aceita `OPENAI_API_KEY` com **`ANIMA_SCENE_IMAGE_ENABLED=1`** (opt-in explícito) em lugar da chave específica, evitando consumir créditos de outras integrações sem autorização. A
configuração não solicita imagens, ZIP ou aprovação por cena. Usa o endpoint
oficial de imagens por padrão. As chamadas da API têm cobrança de uso à
parte, **não estão incluídas na assinatura do ChatGPT**. Cada nova cena pode
gerar um custo e exigir tempo adicional de processamento; a arte gerada é
guardada em `illustrated-backgrounds-v9`, com hash do prompt, modelo e
qualidade, para evitar repetir cobranças em tentativas idênticas.

Com `ANIMA_REQUIRE_ILLUSTRATED_SCENES=1`, o vídeo informa claramente a
ausência ou falha da API, **sem substituir silenciosamente** a ilustração
por montanhas e casas geométricas. Para usar o fallback local de menor
qualidade, defina `ANIMA_REQUIRE_ILLUSTRATED_SCENES=0` (padrão), sem
chave de imagens. O painel informa qual motor de cenário está ativo.

Arquivos: `backend/app/illustrated_scene_engine.py` (prompt, API,
cache), `backend/app/narrated_draw_2d.py` (automação), `backend/app/
official_comic_2d.py` (elenco fixo). A qualidade pode se aproximar da
referência, mas o modelo de imagens não garante reprodução idêntica da
estética em todas as cenas. Sem API de imagem ou outro gerador de imagens
de qualidade equivalente, não há um motor de ilustração generativa de
alta qualidade embutido na VPS.

## Direção de arte por planeta v8

O motor consulta o planeta, bioma, habitantes, marco geográfico e objeto da
missão antes de ilustrar cada trecho da narração. O módulo
`backend/app/planet_art_direction.py` define perfis estáveis por planeta:
Aurora-7 (cristais), Vermelhão (cânions), Oceânia Azul (oceanos),
Flora-Lume/Pétala-3 (jardins), Nuvem Doce (nuvens), Gelus-9 (gelo),
Vulcânia Verde (vulcões), Anel de Safira (estações) e Eco-Lua (vales).
Cada perfil controla céu, relevo, vegetação, arquitetura e espécie nativa.
Outros nomes usam uma identidade estável calculada a partir do nome do planeta.

Dentro do mesmo planeta, `title`, `caption`, `visual_action`, a
fala da cena e o objeto da missão selecionam ações como vila, travessia,
rio, floresta, jardim, pista, oficina, biblioteca, nave ou comemoração.
O posicionamento dos elementos recebe uma semente exclusiva por
cena, mantendo coerência de planeta sem clonar o mesmo desenho.
Habitantes locais só aparecem quando o roteiro descreve interação.
Luna, Tomi e Pipo preservam os desenhos aprovados.
Imagens anteriores não são reutilizadas: cache `story-comic-planet-v8`.

A narração usa voz neural pt-BR por padrão, com ritmo mais calmo
(`ANIMA_NARRATOR_RATE=-8%`), e alterna automaticamente para eSpeak
quando o serviço neural não estiver disponível. Para forçar voz local,
use `ANIMA_TTS_BACKEND=espeak`. A voz neural depende da conectividade
externa do Edge TTS; o motor de ilustração continua local.

**Limitação:** os cenários e nativos são arte procedimental. A mudança
de cenários depende dos temas compreendidos no texto; não equivale a
ilustrações livres geradas por IA nem garante uma interpretação perfeita
de toda frase. A renderização real na VPS ainda precisa ser validada.

## Ajustes de qualidade e FFmpeg v7

- Corrigida a falha de 90% no filtro FFmpeg: a narração agora passa por
  `asplit=2[voice][key]` antes de ser consumida pelo compressor sidechain
  e pela mistura final. A música instrumental fica abaixo da voz.
- Eliminada a moldura retangular interna do cenário da nave; o painel do
  quadrinho permanece, mas Luna, Tomi e Pipo ficam sobre o cenário aberto.
- Balões de fala têm silhueta de nuvem com perímetro contínuo e cauda voltada
  para o personagem. Texto curto e branco com traço azul escuro.
- Colorização do elenco ajustada (rosa, azul, branco e amarelo), cores do
  cenário mais vivas, contraste, leve nitidez e sombras sob os personagens.
- Cache de imagens em `story-comic-v7`, sem reaproveitar a arte anterior.
- Testes de regressão em `tests/test_visual_engine.py` cobrem balão,
  cena de nave e mistura FFmpeg; exigem execução de CI/ambiente de testes.

## Motor de narrativa visual — personagens e cenas v5

- **Elenco fixo:** mantém as formas originais aprovadas de Luna, Tomi e Pipo
  em `approved_cast_embedded.py`. Acrescenta pequenas mudanças de boca e
  sobrancelhas para alegria, dúvida, surpresa, preocupação e concentração.
- **Balões:** palavrinhas curtas de reação, associadas ao personagem que
  fala no roteiro, quando há diálogo correspondente. Não são cópias de
  personagens ou desenhos de outras franquias.
- **História encenada:** o diretor `story_comic_director.py` consulta
  `title`, `caption`, `visual_action`, `action` e falas do storyboard
  para selecionar ambiente, objetos, composição e cor em cada quadrinho.
  Possui cenários desenhados por código (nave, vila, jardim, investigação,
  oficina, mar, biblioteca e outros) com variações determinísticas por cena.
- **Habitantes locais:** criaturas infantis geradas a partir de características
  ambientais e da identidade do planeta. A paleta do planeta permanece estável
  durante o episódio, mas os habitantes aparecem apenas quando a história
  pede. São desenhos procedurais, não imagens geradas por modelo difusivo.
- **Colorização:** o motor preenche regiões fechadas da arte aprovada com cores de pele e uniforme, mantendo os contornos originais e cenário colorido.
- **Desenho em tempo real:** traçado, colorização e prévia continuam
  sincronizados ao trecho de voz de cada cena.
- **Música:** `children_music.py` cria uma trilha original tipo caixinha
  de música, sem royalties ou chamadas de APIs; o FFmpeg mistura com a
  narradora e reduz a música durante a fala.
- **Cache:** a arte usa `story-comic-v7` para impedir que quadros gerados
  por versões anteriores contaminem o resultado.

**Limite conhecido:** esta etapa usa poses da arte-base e variações de expressão
feitas por camadas; ainda não é animação frame-a-frame articulada, nem geração
livre de cenários complexos por uma IA de ilustração. A identidade visual e a
composição são mantidas sem pedir arquivos ao usuário.

## Produção automática e acompanhamento ao vivo

Após a aprovação do roteiro, o sistema gera a narração, desenha os quadrinhos
e codifica os vídeos 16:9 e 9:16 na VPS. **Não exige upload de ZIP/PNG,
token de instalação nem aprovação de imagens individuais.**

A caixa de prévia aparece junto da história. Durante a primeira cena, o
quadro JPEG acompanha o progresso real do FFmpeg; quando um trecho MP4
está concluído, o navegador o reproduz enquanto o próximo é produzido.
Os vídeos finais continuam nos downloads do episódio.

Os personagens **Luna, Tomi e Pipo** da referência aprovada estão
incorporados ao código em `backend/app/approved_cast_embedded.py` como
mapas de contorno comprimidos. Nenhuma ação do usuário é necessária.
O cache de cenas usa a pasta `approved-cast-v3` para ignorar imagens
renderizadas pela versão anterior. As cenas mantêm os rostos e uniformes
aprovados, mas os corpos ainda usam poses estáticas extraídas da
referência; movimentos articulados e novas expressões exigem
rigging/poses adicionais. Um PNG opcional em
`/data/jobs/series/official-model.png` permite usar a prancha maior,
mas **nunca bloqueia** a produção automática.

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
