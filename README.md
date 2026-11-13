# Anima Studio — Cartoon infantil com arte aprovada e animação Blender

Estúdio web dos **Pequenos Guardiões**: roteiro e falas → artes originais com IA → revisão de personagens/cenários → animação de ilustrações no Blender → vídeo com áudio e formatos YouTube/Shorts.

## Mudança de motor artístico

O antigo renderizador que criava bonecos com esferas e armaduras **não é mais chamado** no fluxo de produção de episódios. O novo motor é baseado em imagens de personagens e cenários **explicitamente aprovadas**. Se faltar uma imagem, a API retorna 409 com os identificadores pendentes. Ela nunca troca o projeto visual por bonecos procedurais.

A primeira integração de animação usa **planos ilustrados em Blender (2.5D, com Cycles CPU)**. Ela permite câmera, profundidade básica, deslocamento suave, balanço corporal e reações à fala por mudança de escala. **Não oferece ainda rig de membros, expressões faciais deformáveis nem sincronia labial verdadeira**. Esses recursos exigem a produção de recortes/poses e uma etapa adicional de rigging. Não confunda um PNG plano com personagem 3D completamente modelado.

## Produção no painel

1. Crie o roteiro na página principal e escolha os formatos.
2. Entre na [Central de Arte](/arte.html) do próprio estúdio.
3. Conecte o agente ComfyUI do seu Windows (configuração em `docs/integracao-comfyui.md`). O token `ANIMA_COMFY_TOKEN` fica na variável secreta do iContainer e na sessão do navegador; nunca publique-o.
4. Selecione o episódio e formato. Use **Gerar imagens que faltam** para enviar os prompts à fila ComfyUI; selecione cada tarefa, visualize e aprove. Também é possível carregar PNGs prontos e aprová-los diretamente.
5. Os personagens Luna, Tomi e Pipo exigem PNG com transparência real; imagens com fundo uniformemente branco geradas no ComfyUI podem ser recortadas automaticamente **no momento da aprovação**. Fundo complexo requer recorte externo e envio de PNG transparente.
6. Cada cena requer seu background ilustrado na proporção do vídeo. A aprovação é persistente em `ANIMA_STORAGE/<job_id>/art/approved/`.
7. Com todos os materiais aprovados, clique em **Renderizar arte aprovada** no painel. O Blender posiciona e move os PNGs aprovados, FFmpeg sincroniza as vozes e gera MP4.

ComfyUI é um gerador externo conectado ao painel, não um serviço incluído no ChatGPT Plus. O agente deve estar online para produzir as imagens. A qualidade dos candidatos depende do checkpoint, do fluxo ComfyUI e da aprovação artística.

## Endpoints para integrar/diagnosticar

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

A página principal fica em `http://localhost:5000` e a Central de Arte em `http://localhost:5000/arte.html`.

## Verificações

- `python -m unittest discover -s backend/tests -v` valida roteiro, aprovação PNG, pipeline de áudio/FFmpeg e frames Blender quando as dependências estão instaladas.
- O GitHub Actions executa testes, valida o painel e constrói o Docker.
- Os PNGs simples criados nos testes são **somente fixtures técnicas**, nunca personagens de produção ou fallback artístico.

## Segurança e limitações

Proteja o painel com HTTPS e autenticação/restrições de acesso antes de disponibilizar ao público. Os endpoints de geração e aprovação artística exigem `ANIMA_COMFY_TOKEN`; o restante da API tem pontos de acesso administrativos que também devem ser protegidos na implantação.

O agente ComfyUI mantém a fila em memória; reiniciar a API interrompe tarefas pendentes. Imagens **já aprovadas** são persistidas. A qualidade final ainda depende de gerar personagens consistentes, sem artefatos, e aprimorar o rigging.
