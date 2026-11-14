# Anima Studio — Cartoon infantil com arte aprovada e animação Blender

Estúdio web dos **Pequenos Guardiões**: roteiro aprovado → geração automática de artes com IA → validação técnica das imagens → animação de ilustrações no Blender → vídeo com áudio e formatos YouTube/Shorts.

## Mudança de motor artístico

O antigo renderizador que criava bonecos com esferas e armaduras **não é mais chamado** no fluxo de produção de episódios. O novo motor é baseado em imagens de personagens e cenários **validadas tecnicamente pelo pipeline automático**. Se faltar uma imagem, a API retorna 409 com os identificadores pendentes. Ela nunca troca o projeto visual por bonecos procedurais.

A primeira integração de animação usa **planos ilustrados em Blender (2.5D, com Cycles CPU)**. Ela permite câmera, profundidade básica, deslocamento suave, balanço corporal e reações à fala por mudança de escala. **Não oferece ainda rig de membros, expressões faciais deformáveis nem sincronia labial verdadeira**. Esses recursos exigem a produção de recortes/poses e uma etapa adicional de rigging. Não confunda um PNG plano com personagem 3D completamente modelado.

## Produção automática no painel único

1. Clique em **Criar roteiro**: a história, o planeta, as falas e o storyboard aparecem no próprio painel.
2. Clique em **Aprovar roteiro e produzir vídeo**: o servidor inicia a geração pelo primeiro motor configurado (Runway API, OpenAI Images API ou ComfyUI local). A fila é persistida em `ANIMA_STORAGE/comfyui/task-state.json`; se nenhum motor estiver disponível, o painel explica por que o processamento não começou, sem pedir fotos.
3. **Luna, Tomi e Pipo** são gerados e fixados automaticamente **uma única vez** na série. Os PNGs oficiais ficam em `ANIMA_STORAGE/series/characters/official/`, com hash SHA-256 e trava de identidade. Nenhum episódio pode regenerá-los ou substituí-los pela interface comum.
4. Cada novo planeta produz somente as artes dos **cenários do episódio**; 16:9 e 9:16 usam fundos próprios, mas os mesmos personagens oficiais. O sistema mostra automaticamente as miniaturas embaixo do roteiro e permite ampliar a imagem sem sair da página.
5. O motor de imagens configurado entrega PNGs ao servidor. Um coordenador persistente valida formato, tamanho, transparência e hash, recorta automaticamente o fundo branco uniforme dos protagonistas, solicita nova tentativa quando a imagem é tecnicamente inválida (até duas tentativas adicionais) e salva os arquivos aprovados. **Essas verificações não substituem uma avaliação estética por visão computacional.**
6. Quando os personagens oficiais e cenários estão prontos, o sistema inicia **automaticamente o Blender Cycles CPU e FFmpeg**, sem botão de montagem. A tela mostra o andamento e os arquivos MP4 disponíveis. Se o Blender falhar, o erro fica visível; o sistema não reinicia vídeos pesados indefinidamente.
7. O usuário não precisa enviar imagens, digitar token na tela, aprovar uma por uma nem abrir outra página. O token do agente ComfyUI fica configurado como segredo do servidor e no computador que executa o agente.

O motor não cria bonecos geométricos como substitutos. Quando nenhuma API de imagem ou estação ComfyUI está online, o painel mostra **Motor de imagens indisponível** e mantém a fila salva; não afirma que uma imagem foi gerada antes de receber o arquivo verdadeiro.

### Motores de imagem — seleção automática

No painel iContainer, configure **uma vez** as variáveis de ambiente do container da aplicação (não no terminal do host sem repassá-las ao Docker):

- `ANIMA_IMAGE_PROVIDER=auto` (padrão): usa `RUNWAYML_API_SECRET` ou `RUNWAY_API_KEY` quando presente; caso contrário, `OPENAI_API_KEY`; sem nenhuma, usa o agente ComfyUI se estiver conectado.
- `ANIMA_IMAGE_PROVIDER=runway` + `RUNWAYML_API_SECRET`: usa diretamente a API Runway (modelo padrão `nano_banana_2.1`; selecione com `ANIMA_RUNWAY_IMAGE_MODEL`).
- `ANIMA_IMAGE_PROVIDER=openai` + `OPENAI_API_KEY`: usa a API de imagens da OpenAI (modelo padrão `gpt-image-1.5`; selecione com `ANIMA_OPENAI_IMAGE_MODEL`, qualidade com `ANIMA_IMAGE_QUALITY`).
- `ANIMA_IMAGE_PROVIDER=comfyui`: usa somente o agente local Windows/RX 580, com token `ANIMA_COMFY_TOKEN` configurado no servidor e na estação.

**As APIs Runway e OpenAI podem cobrar a cada imagem gerada.** Uma assinatura ChatGPT Plus não fornece chave de API nem créditos de geração na VPS. O sistema nunca tenta acessar as conversas do ChatGPT como substituto da API. Não coloque chaves no GitHub nem na página pública.

O endpoint `GET /api/image-engine/status` mostra qual motor está selecionado e se está pronto **sem revelar chaves**. Após alterar as variáveis no iContainer, recrie a aplicação preservando `/data/jobs`. Tarefas antigas pendentes podem ser retomadas pelo motor recém-conectado.

Para operar sem API paga, conecte o agente ComfyUI, instale um checkpoint adequado e defina `ANIMA_COMFY_TOKEN` na aplicação. Veja `docs/integracao-comfyui.md`. O modelo de imagem utilizado pode afetar bastante a qualidade. O sistema valida tecnicamente o arquivo recebido, mas não pode garantir que a imagem gerada tenha qualidade artística profissional ou consistência perfeita antes de renderizar.

## Endpoints para integrar/diagnosticar

- `POST /api/jobs/{id}/story/approve`: aprovar roteiro, enfileirar as imagens no motor selecionado e habilitar a montagem automática quando estiverem prontas.
- `GET /api/image-engine/status`: disponibilidade e modelo selecionado do motor de imagens.
- `GET /api/jobs/{id}/art/board`: estado de todos os personagens oficiais, cenários, aprovações e tarefas em fila.
- `GET /api/jobs/{id}/art/candidate/{task_id}`: imagem candidata para revisão na própria página.
- `GET /api/jobs/{id}/art/approved/{asset_id}?fmt=9:16`: imagem oficial aprovada.
- `GET /api/jobs/{id}/art-plan?fmt=9:16`: referência visual, prompts e lista de cenas.
- `GET /api/jobs/{id}/art/status?fmt=9:16`: aprovação e arquivos faltantes.
- `POST /api/jobs/{id}/art/generate`: enfileirar artes no ComfyUI (token Bearer; body `{"format":"9:16"}`).
- `POST /api/jobs/{id}/art/approve/{task_id}`: validar e aprovar uma imagem ComfyUI (Bearer).
- `POST /api/jobs/{id}/art/upload/{asset_id}?fmt=9:16`: enviar PNG aprovado no corpo da requisição (Bearer).
- `POST /api/jobs/{id}/render`: gerar vídeo somente com arte aprovada.
- `GET /api/jobs/{id}/render-status`: progresso, quadros e eventos recentes.
- `GET /api/health/3d`: verificar Blender dentro do container.
- `GET /api/diagnostics`: diagnosticar dependências e instalação do Blender.

Os personagens aprovados são compartilhados entre 9:16 e 16:9. Os cenários são específicos por formato. Cada aprovação associa um SHA-256 ao arquivo e trava a identidade visual pelo `identity_lock` do elenco.

## Ambiente e deploy

A VPS iContainer pode usar uma imagem `python:3.13.0` genérica e **ignorar o Dockerfile**. Instalar Blender à mão dentro desse container não resiste à sua recriação. O bootstrap tenta recuperar dependências na inicialização com root+apt-get, mas o melhor é construir a imagem personalizada com o Dockerfile.

O novo renderizador usa Cycles em **CPU**, por isso não exige GPU CUDA/HIP no servidor e evita depender diretamente do contexto Eevee/OpenGL que apresentou segmentation fault no container anterior. A execução de uma cena de teste em CI não garante desempenho em episódios completos. O motor gera PNGs intermediários e o FFmpeg compõe e codifica os vídeos finais.

Os arquivos de episódio e aprovações ficam no volume persistente `/data/jobs`. Não remova esse volume ao atualizar a aplicação. Código enviado ao GitHub **não instala automaticamente a atualização no iContainer**: faça o deploy da versão nova pelo painel.

### Executar a imagem Docker local

```bash
docker compose up -d --build
```

A única página de produção fica em `http://localhost:5000`. A antiga `/arte.html` permanece disponível apenas para compatibilidade, mas não faz parte do fluxo normal.

## Verificações

- `python -m unittest discover -s backend/tests -v` valida roteiro, aprovação PNG, pipeline de áudio/FFmpeg e frames Blender quando as dependências estão instaladas.
- O GitHub Actions executa testes, valida o painel e constrói o Docker.
- Os PNGs simples criados nos testes são **somente fixtures técnicas**, nunca personagens de produção ou fallback artístico.

## Segurança e limitações

Proteja o painel com HTTPS e autenticação/restrições de acesso antes de disponibilizar ao público. Os endpoints de geração e aprovação artística exigem `ANIMA_COMFY_TOKEN`; o restante da API tem pontos de acesso administrativos que também devem ser protegidos na implantação.

A fila de tarefas ComfyUI é persistida em disco e tarefas em execução no momento do reinício retornam para a fila. Imagens **já aprovadas** permanecem persistentes. O estado das artes fica salvo nos metadados da série e dos episódios. O coordenador automático retoma episódios elegíveis após reinicialização do serviço. A qualidade final ainda depende de gerar personagens consistentes, sem artefatos, e aprimorar o rigging.
