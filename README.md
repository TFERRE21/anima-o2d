# Anima Studio — Cartoon infantil com arte aprovada e animação Blender

Estúdio web dos **Pequenos Guardiões**: roteiro e falas → artes originais com IA → revisão de personagens/cenários → animação de ilustrações no Blender → vídeo com áudio e formatos YouTube/Shorts.

## Mudança de motor artístico

O antigo renderizador que criava bonecos com esferas e armaduras **não é mais chamado** no fluxo de produção de episódios. O novo motor é baseado em imagens de personagens e cenários **explicitamente aprovadas**. Se faltar uma imagem, a API retorna 409 com os identificadores pendentes. Ela nunca troca o projeto visual por bonecos procedurais.

A primeira integração de animação usa **planos ilustrados em Blender (2.5D, com Cycles CPU)**. Ela permite câmera, profundidade básica, deslocamento suave, balanço corporal e reações à fala por mudança de escala. **Não oferece ainda rig de membros, expressões faciais deformáveis nem sincronia labial verdadeira**. Esses recursos exigem a produção de recortes/poses e uma etapa adicional de rigging. Não confunda um PNG plano com personagem 3D completamente modelado.

## Produção automática no painel único

1. Clique em **Criar roteiro**: a história, o planeta, as falas e o storyboard aparecem no próprio painel.
2. Clique em **Aprovar roteiro e gerar imagens**: o servidor dispara imediatamente a fila ComfyUI, sem abrir outra página. A fila é persistida em `ANIMA_STORAGE/comfyui/task-state.json`; se a estação RX 580 estiver desligada, as tarefas aguardam a próxima conexão.
3. **Luna, Tomi e Pipo** são gerados/aprovados **uma única vez** na série. Os PNGs oficiais ficam em `ANIMA_STORAGE/series/characters/official/`, com hash SHA-256 e trava de identidade. Nenhum episódio pode regenerá-los ou substituí-los pela interface comum.
4. Cada novo planeta produz somente as artes dos **cenários do episódio**; 16:9 e 9:16 usam fundos próprios, mas os mesmos personagens oficiais. O sistema mostra automaticamente as miniaturas embaixo do roteiro e permite ampliar a imagem sem sair da página.
5. Aperte **Aprovar** em cada arte válida ou **Refazer** na cena escolhida. A geração é automática, mas a aprovação é editorial e usa o token `ANIMA_COMFY_TOKEN` informado uma vez no mesmo painel, apenas na sessão do navegador.
6. O botão **Montar vídeo com artes aprovadas** é desbloqueado depois de os personagens oficiais e todos os cenários necessários estarem aprovados. Blender Cycles CPU anima os planos ilustrados e FFmpeg sincroniza as vozes e monta o MP4.

O motor não cria bonecos geométricos como substitutos. Se o gerador de imagens estiver offline, o painel mostra **Aguardando o agente ComfyUI** e mantém a fila salva; não afirma que uma imagem foi gerada antes de receber o arquivo verdadeiro. ComfyUI roda na sua estação Windows/RX 580; não é um recurso incluído na assinatura ChatGPT Plus.

Uma primeira configuração precisa conectar o agente ComfyUI, instalar um checkpoint adequado e definir `ANIMA_COMFY_TOKEN` na aplicação. Veja `docs/integracao-comfyui.md`. O modelo de imagem utilizado pode afetar bastante a qualidade; o fluxo não garante uma ilustração profissional sem revisão humana.

## Endpoints para integrar/diagnosticar

- `POST /api/jobs/{id}/story/approve`: aprovar roteiro e criar a fila de imagens sem intervenção adicional no painel.
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

A fila de tarefas ComfyUI é persistida em disco e tarefas em execução no momento do reinício retornam para a fila. Imagens **já aprovadas** permanecem persistentes. O estado de aprovação fica salvo nos metadados da série e dos episódios. A qualidade final ainda depende de gerar personagens consistentes, sem artefatos, e aprimorar o rigging.
