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

## Diagnóstico no Windows/RX 580

Quando o agente mostra `RuntimeError: ComfyUI marcou a execução como erro`,
a conexão com a VPS já funcionou. É o motor local quem não conseguiu gerar
a imagem. Na instalação Windows, verifique primeiro:

```powershell
Invoke-RestMethod http://127.0.0.1:8188/system_stats |
  ConvertTo-Json -Depth 5

Get-ChildItem "C:\ComfyUI-Zluda\ComfyUI-Zluda\models\checkpoints" -File |
  Select-Object Name,Length

$historico = Invoke-RestMethod "http://127.0.0.1:8188/history?max_items=5"
foreach ($item in $historico.PSObject.Properties) {
  if ($item.Value.status.status_str -eq "error") {
    Write-Host "Tarefa ComfyUI:" $item.Name
    $item.Value.status.messages | ConvertTo-Json -Depth 8
  }
}
```

Não envie senhas, variáveis secretas ou tokens junto com o diagnóstico.
As mensagens `execution_error` contêm nome do nó, tipo de exceção e
motivo. Se for falta de checkpoint, instale o modelo solicitado ou configure
`ANIMA_ART_CHECKPOINT` para um checkpoint compatível já instalado.
Se for memória, diminua a resolução do trabalho e analise os limites
da RX 580 com ZLUDA em FP32. A conexão `ready: true` significa apenas
agente conectado, **não** geração de imagem comprovada.

Após atualizar a cópia local do repositório com `git pull --ff-only`,
reinicie o script `iniciar-comfyui-agent.ps1` para que os diagnósticos
novos sejam exibidos. O agente envia `heartbeat` durante as gerações
demoradas para não aparecer desconectado indevidamente na VPS.

## RX 580 / ZLUDA: resolução adaptativa por falta de VRAM

A RX 580 em modo ZLUDA + FP32 pode detectar 8 GB de VRAM e ainda
apresentar `Nó 5 (KSampler): CUDA error: out of memory` quando tenta
gerar o retrato em 768×1024 e cenários em 576×1024. A configuração
`NOVRAM` não garante que o sampler nunca aloque memória na GPU.

O agente Windows identifica `RX 580` em `/system_stats` e ativa, por
padrão, o perfil de memória `rx580-memory-safe-v1`. Resoluções de
**difusão** (não confundir com a resolução final do vídeo):

- Personagens: 448×640; quando ocorre OOM, 384×512
- Cenas verticais: 384×704; fallback 320×576
- Cenas horizontais: 704×384; fallback 576×320

Cada tarefa só usa o fallback se a primeira execução realmente falhar por
falta de memória; pode solicitar `POST /free` para descarregar modelos.
O resultado é ampliado pelo processador (Pillow/Lanczos) antes de enviar
à VPS no tamanho previsto no roteiro. Esse redimensionamento **não cria
detalhes novos** e a qualidade estética precisa ser avaliada. Como padrão,
o agente não reduz a resolução para outros modelos de GPU.

Quando o agente atualizado se registra com
`profile_version=rx580-memory-safe-v1`, o servidor pode retomar **uma
única vez** tarefas do mesmo roteiro anteriormente marcadas com erro de
memória; não exige gerar ou aprovar outro roteiro. Se mesmo o novo perfil
falhar, a aplicação mostra o bloqueio de memória e evita tentativas
ilimitadas. Não é uma garantia de que todo modelo de IA rode na RX 580;
checkpoints mais pesados podem continuar exigindo outra GPU.

Para ativar a correção:

1. Atualize o código da VPS e o clone local preservando `/data/jobs`
   e os checkpoints existentes
2. Reinicie **somente o agente** com
   `cd C:\AnimaStudio\anima-o2d; git pull --ff-only` e depois
   `cd .\tools\windows-gpu-agent; .\iniciar-comfyui-agent.ps1`
3. Mantenha o processo ComfyUI aberto na porta `8188`.
   Se ele estiver em estado persistente de OOM, encerre apenas
   o processo ComfyUI conhecido e reinicie-o; não reinstale ZLUDA

Use `ANIMA_RX580_MEMORY_PROFILE=0` no Windows somente para desativar
voluntariamente o ajuste. Se necessário, aumente `COMFY_TASK_TIMEOUT`
para `1800` para imagens geradas lentamente pelo modo FP32.

## Limitações desta primeira versão
- O agente usa um workflow exportado pelo usuário em formato API; não modifica o workflow visual.
- O fluxo entrega imagens geradas pelo ComfyUI ao painel; o Blender/FFmpeg monta automaticamente o episódio quando todas as imagens são aprovadas tecnicamente. A animação atual é 2.5D, não rigging completo.
- A fila de imagens é persistida em disco em `ANIMA_STORAGE/comfyui/task-state.json`, e as tarefas ativas são reencaminhadas após reinício.
- Configure armazenamento persistente para `ANIMA_STORAGE`.
- O token protege os endpoints, mas a página é uma interface técnica; não publique o token em links, capturas ou repositórios.
