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

## Windows — inicialização automática do ComfyUI

1. Abra o PowerShell.
2. Na cópia local do projeto, execute `cd C:\AnimaStudio\anima-o2d; git pull --ff-only`.
3. Entre em `cd .\tools\windows-gpu-agent`.
4. Execute `Set-ExecutionPolicy -Scope Process Bypass` e `.\iniciar-comfyui-agent.ps1`.
5. Informe a URL pública do Anima Studio e o mesmo token `ANIMA_COMFY_TOKEN` da VPS.

**Não precisa abrir o `comfyui.bat` separadamente:** no Windows, se o agente não
encontrar uma API em `http://127.0.0.1:8188/system_stats`, ele inicia
automaticamente `C:\ComfyUI-Zluda\ComfyUI-Zluda\comfyui.bat` em outra
janela de console, aproveitando a instalação existente.
Se a porta estiver ocupada, não inicia uma segunda instância.
Se o ComfyUI encerrar, o agente deixará de enviar sinal de pronto à VPS,
tentará reabri-lo e voltará a se registrar quando ele estiver acessível.

Para evitar um ciclo de reinícios se a RX 580 continuar apresentando OOM,
o agente limita as tentativas automáticas a **três inicializações por hora**
e mantém ao menos 90 segundos entre elas. Essa limitação é intencional.
As mensagens da janela do ComfyUI devem ser consultadas se o processo
não conseguir iniciar ou se voltar a encerrar. Os processos dependem
do computador permanecer ligado e sem suspensão.

O caminho pode ser alterado com `COMFYUI_INSTALL_DIR` no Windows.
Para desativar a inicialização automática, configure
`ANIMA_COMFY_AUTOSTART=0` no Windows.

O agente usa o Python do ambiente virtual ComfyUI e instala/verifica `requests`.
Mantenha o agente aberto enquanto quiser receber tarefas. Para operar após
reinícios do Windows sem abrir o PowerShell manualmente, configure uma
tarefa agendada segura em sua conta Windows (o instalador não cria essa tarefa
e não armazena o token automaticamente).

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

## Opcional: UNet FP16 quando KSampler falha até em 384×512

Se a RX 580/ZLUDA permanece com `CUDA error: out of memory`
mesmo após as duas resoluções reduzidas, **reduzir mais pixels
isoladamente não garante solucionar o erro**. O checkpoint pode estar sendo
executado em precisão FP32, aumentando o uso de VRAM, e versões antigas de
ZLUDA/PyTorch também podem ter limitações de compatibilidade. Há relatos
desse mesmo problema com RX 580 e PyTorch 2.3.0.

Existe um procedimento **experimental e reversível** para reduzir a memória
dos pesos do UNet sem mudar o modelo ou instalar outro programa:

1. Encerre o agente Anima Studio com `Ctrl+C` e encerre **somente**
   o console da instância ComfyUI em `127.0.0.1:8188`
2. Na pasta do clone Anima Studio no Windows, atualize com
   `cd C:\AnimaStudio\anima-o2d; git pull --ff-only`
3. Execute `cd .\tools\windows-gpu-agent`
4. Verifique o launcher:
   `.\perfil-rx580-zluda.ps1 -Modo verificar`
5. Se ele encontrar `--force-fp32` ou `--fp32-unet` nas
   linhas ativas de `comfyui.bat`, aplique:
   `.\perfil-rx580-zluda.ps1 -Modo fp16`
6. Reinicie o agente `.\iniciar-comfyui-agent.ps1`. O agente iniciará
   o ComfyUI, que agora tentará rodar o UNet com `--fp16-unet`.
   Confirme que o console não informa mais `Forcing FP32`

O script salva antes uma cópia byte-a-byte do `comfyui.bat`.
Se surgir erro de operações FP16 incompatíveis, encerre a instância
ComfyUI e execute
`.\perfil-rx580-zluda.ps1 -Modo restaurar` e reinicie o agente.
O script não altera PyTorch, ZLUDA, modelos, pastas nem checkpoints.
**Nem toda GPU RX 580 executará FP16 com essa instalação**.

Para tentar novamente **o mesmo roteiro** sem clicar em aprovar,
a VPS precisa estar atualizada: se o agente reconhecer
`rx580-unet-fp16-v2` e o servidor também suportar esse perfil,
as tarefas anteriormente bloqueadas pelo erro de GPU poderão ser
reencaminhadas **somente uma vez**. Uma geração concluída na GPU
ainda não foi demonstrada; o próximo passo é confirmar a primeira
imagem real. A resolução de saída do vídeo permanece inalterada.

Se FP16 também não gerar imagens, o caminho viável sem créditos
pode exigir um motor alternativo local (por exemplo CPU/DirectML)
ou outra GPU. Não afirmar que mais redução de resolução, NOVRAM
ou cópias de RAM necessariamente consertarão o KSampler.

## Alternativa sem créditos: DirectML separado do ZLUDA

**Motivo:** se a RX 580 com CUDA/ZLUDA + PyTorch 2.3 continuar a
falhar em `KSampler.calculate_sigmas` com `CUDA error: out of memory`
em 0,42 segundo, reduzir para 384×512 ou usar somente FP16 pode não
resolver. O DirectML usa o Windows/DirectX 12 para operar na GPU AMD,
sem passar pelo CUDA/ZLUDA. O ComfyUI documenta o argumento
`--directml`; sua compatibilidade com o PC real exige validação.

O instalador `instalar-directml-rx580.ps1` cria um clone
**independente e travado em ComfyUI v0.3.10** e um `venv-directml`
separado no diretório `C:\AnimaStudio\ComfyUI-DirectML`.
Utiliza Python 3.11 e o pacote `torch-directml==0.2.5.dev240914`
com PyTorch 2.4.1. O checkpoint é compartilhado via um arquivo
`anima-modelos.yaml`, sem duplicar ou sobrescrever os modelos.
Não altera `C:\ComfyUI-Zluda`, não executa `fixforrx580.bat`,
não instala HIP adicional e não apaga o roteiro da VPS.

No **Windows**, com Git e Python 3.11 instalados:

```powershell
cd C:\AnimaStudio\anima-o2d
git pull --ff-only
cd .\tools\windows-gpu-agent
Set-ExecutionPolicy -Scope Process Bypass
.\instalar-directml-rx580.ps1 -Modo verificar
.\instalar-directml-rx580.ps1 -Modo instalar
```

A instalação não inicia automaticamente o motor. Para usar DirectML,
**encerre a instância ZLUDA na porta 8188 e pare o agente antigo**.
O script não mata processos; exibe conflito e preserva a instalação.
Depois, abra somente o agente Windows com:

```powershell
$env:ANIMA_GPU_BACKEND="directml"
.\iniciar-comfyui-agent.ps1
```

O agente detecta a instalação DirectML e inicia seu `comfyui.bat`
na porta 8188, sem abrir uma segunda instância. Para usar ZLUDA
novamente, encerre DirectML e execute no PowerShell:
`$env:ANIMA_GPU_BACKEND="zluda"`; depois reinicie o agente.

Em `/system_stats`, um ComfyUI DirectML costuma exibir dispositivo
`privateuseone`, não `cuda:0`. O agente só reporta
`rx580-directml-v3` quando o dispositivo local realmente aponta
para DirectML. Com a aplicação VPS atualizada, o perfil novo pode
recuperar **uma vez** as imagens bloqueadas por OOM do ZLUDA; não
precisa alterar o roteiro nem enviar PNGs. Se DirectML também falhar,
as tentativas são limitadas, e será preciso investigar o log local
ou usar outro motor/gpu; o código não inventa imagens.

**Limitação:** o DirectML pode ser mais lento, tem suporte limitado a
algumas operações/modelos e o backend PyTorch-DirectML é um pacote
legado. A instalação é uma alternativa prática a ser validada, não
uma garantia de vídeo concluído ou qualidade de estúdio.

## Limitações desta primeira versão
- O agente usa um workflow exportado pelo usuário em formato API; não modifica o workflow visual.
- O fluxo entrega imagens geradas pelo ComfyUI ao painel; o Blender/FFmpeg monta automaticamente o episódio quando todas as imagens são aprovadas tecnicamente. A animação atual é 2.5D, não rigging completo.
- A fila de imagens é persistida em disco em `ANIMA_STORAGE/comfyui/task-state.json`, e as tarefas ativas são reencaminhadas após reinício.
- Configure armazenamento persistente para `ANIMA_STORAGE`.
- O token protege os endpoints, mas a página é uma interface técnica; não publique o token em links, capturas ou repositórios.
