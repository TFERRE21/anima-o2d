# Integração ComfyUI — Anima Studio

## Arquitetura
- A VPS expõe uma fila autenticada em `/api/comfy`.
- O agente Windows inicia conexões de saída HTTPS e acessa o ComfyUI somente em `127.0.0.1:8188`.
- Não exponha a porta 8188 à internet.
- O agente executa o workflow local e envia o PNG final à VPS.

## Configuração da VPS
Configure uma variável secreta de ambiente chamada `ANIMA_COMFY_TOKEN` com um valor aleatório forte. Exemplo para gerar localmente no PowerShell: `[guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N")`. Não grave o token no Git.

A aplicação deve ser redeployada após configurar o secret.

## Preparar o workflow API do ComfyUI
1. Abra o ComfyUI no Windows.
2. Ative o modo de desenvolvedor nas configurações.
3. Use Save (API Format) / Export API workflow para salvar o workflow JSON.
4. Salve como `workflow_api.json` dentro de `tools/windows-gpu-agent`.
5. Confira se contém os nós `CheckpointLoaderSimple`, `CLIPTextEncode` (positivo e negativo), `KSampler`, `EmptyLatentImage` e `SaveImage`.
6. O checkpoint configurado no painel deve existir em `ComfyUI/models/checkpoints`.

## Windows
Com o ComfyUI já aberto e funcional:
1. Abra PowerShell.
2. Entre na pasta `tools/windows-gpu-agent` do clone local do repositório.
3. Execute `Set-ExecutionPolicy -Scope Process Bypass`.
4. Execute `./iniciar-comfyui-agent.ps1`.
5. Informe a URL pública do Anima Studio e o mesmo token configurado na VPS.

O agente usa o Python do ambiente virtual ComfyUI e instala/verifica `requests`. Mantenha o processo aberto enquanto quiser receber tarefas.

## Painel
Abra `/ai-studio.html`, informe o token e clique em Testar conexão. A geração só é aceita quando o agente estiver online. As tarefas são registradas e as imagens PNG são armazenadas em `ANIMA_STORAGE/comfyui`.

## Limitações desta primeira versão
- O agente usa um workflow exportado pelo usuário em formato API; não modifica o workflow visual.
- O fluxo entrega imagens geradas pelo ComfyUI ao painel. A integração automática de rigs/cenas OpenToonz e a renderização de episódios completos são etapas posteriores.
- A fila atual é mantida em memória da API; reiniciar o processo da VPS limpa tarefas pendentes.
- Configure armazenamento persistente para `ANIMA_STORAGE`.
- O token protege os endpoints, mas a página é uma interface técnica; não publique o token em links, capturas ou repositórios.
