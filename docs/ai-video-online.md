# Geração de vídeo com IA online

O Anima Studio possui um fluxo de teste de geração online usando fal.ai:

- Imagem-chave: `fal-ai/flux-pro/v1.1`
- Animação da imagem: `fal-ai/kling-video/v3/pro/image-to-video`
- API interna: `POST /api/ai-video/test`
- Acompanhamento: `GET /api/ai-video/jobs/{job_id}`
- Arquivos: `/app/data/jobs/ai-video/{job_id}/`

## Configuração obrigatória

Configure `FAL_KEY` como variável secreta no painel de ambiente do iContainer para o serviço Anima Studio. Não coloque a chave no HTML, GitHub, nem em mensagens. Reinicie somente o container `animacao2d` após salvar a variável.

O endpoint retorna HTTP 503 com instruções se a chave não estiver configurada. A chave é lida apenas no backend.

## Teste

Na página **Criar episódio**, use o cartão **Produção com IA online — FLUX + Kling 3.0**. O teste gera uma imagem-chave, anima a imagem em um clipe de 5, 10 ou 15 segundos e salva o MP4 e o quadro no armazenamento persistente. O navegador consulta o estado em intervalos de 4 segundos.

Esse fluxo é uma prova real de geração de cena por IA online. Ele não substitui ainda a renderização integral de um episódio de 60–90 segundos, nem sincroniza as falas do roteiro com vários planos. Isso requer o pipeline multi-cena e referências persistentes dos personagens.

## Custos

A geração é cobrada pela fal.ai conforme o modelo e a duração selecionados. Verifique os preços atuais no painel fal.ai antes de iniciar. O teste padrão usa um único quadro FLUX e um clipe Kling de 5 segundos.
