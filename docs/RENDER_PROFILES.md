# ANIMA STUDIO 3D — perfis de renderização

Este documento registra o perfil estável de renderização antes do experimento com a GPU local RX 580.

## Perfil estável (VPS / CPU)

Arquivo: `backend/app/blender_scene.py`

- Engine: Eevee Next quando disponível (Workbench apenas como fallback de compatibilidade).
- Resolução interna: 100%.
- Eevee temporal samples: 8.
- Threads: variável `ANIMA_BLENDER_THREADS`; padrão automático limitado a 6 núcleos.
- FPS de trabalho: 12.
- Saída final: 1080x1920 para Shorts e 1920x1080 para vídeos horizontais.
- Intermediários: PNG RGB sem perdas; compressão PNG configurada em 5.
- FFmpeg: H.264, CRF 20, preset ultrafast.

### Retorno ao perfil estável

Manter o deploy da branch `main` e não definir `ANIMA_RENDER_SCALE` abaixo de 100 nem `ANIMA_EEVEE_SAMPLES` abaixo de 8. Para garantir explicitamente:

```env
ANIMA_RENDER_SCALE=100
ANIMA_EEVEE_SAMPLES=8
ANIMA_BLENDER_THREADS=6
```

A quantidade de threads deve ser ajustada à CPU real do host. Esse perfil é o fallback caso o agente Windows/RX 580 não seja aprovado nos testes.

## Perfil experimental — RX 580 / Windows 10

A experiência será isolada na branch `gpu-rx580-experimental`. Não substituir a produção VPS/CPU antes de medir:
- GPU e driver detectados no Windows;
- backend OpenGL reportado pelo Blender;
- engine Eevee disponível;
- render de cena de teste concluído;
- tempo por quadro, FPS efetivo e ausência de erro;
- qualidade visual conferida lado a lado.

A RX 580 (Polaris) não deve ser tratada como compatível com HIP para Cycles. O teste inicial é Eevee via OpenGL. O script de diagnóstico não altera o projeto nem configura a VPS.

## Metas de desempenho (a validar, não garantidas)

- Short de 60–90 s: meta de até 2 min.
- Vídeo de até 10 min: meta de até 10 min.

Os prazos dependem da complexidade das cenas, número de quadros, GPU, CPU, transferência de arquivos e codificação. Só considerar atingidos após benchmark completo de ponta a ponta.
