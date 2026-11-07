# Pipeline de histórias e animação 2D

## Regra central

**Nenhum vídeo começa a ser renderizado antes de o motor criar e salvar uma história original.** O roteiro deve definir planeta, habitantes, problema, pistas, diálogos/ações, solução e valor educativo. O mesmo trio principal aparece em todas as aventuras, mas cada história acontece em um planeta com identificador não repetido.

## Etapas do episódio manual

1. **Planejamento da história:** o motor escolhe um planeta ainda não usado, um bioma, habitantes, um desafio e uma lição educativa.
2. **Roteiro completo:** escreve a narração e os diálogos de Luna, Tomi e Pipo em português brasileiro.
3. **Roteiro Shorts:** seleciona o momento mais impactante (pista, virada e solução) e monta uma sequência curta própria, com falas e cenas específicas.
4. **Storyboard:** prepara 12 cenas com título, legenda curta e ação visual.
5. **Prévia e revisão:** o painel mostra planeta, sinopse, valor, narração, falas individuais dos personagens, trecho escolhido para o Short e storyboard.
6. **Aprovação do usuário:** somente após clicar em “Aprovar roteiro e gerar vídeos 2D” a fila de renderização começa.
7. **Animação:** personagens consistentes, fundos próprios do planeta, elementos da missão e movimentos procedurais.
8. **Áudio:** narrador e personagens recebem vozes diferenciadas em português brasileiro; Pipo tem uma entrega mais aguda. O renderizador alterna os segmentos e mede a duração total.
9. **Render duplo:** versões horizontais e verticais com composições e tempos próprios.
10. **Controle de qualidade:** conferir duração, arquivo MP4, áudio, legibilidade, continuidade visual e adequação para crianças.
11. **Revisão e publicação:** aprovação editorial separada e envio ao YouTube somente após autorização do canal.

## Contrato de duração obrigatório

| Perfil | Resolução | Duração |
|---|---:|---:|
| Episódio principal 16:9 | 1920×1080 | **Entre 5 e 10 minutos** (301–600 segundos) |
| Shorts 9:16 | 1080×1920 | **Entre 60 e 90 segundos** |

O episódio horizontal usa `audio_segments_long`, alternando narrador e diálogos separados por personagem. O Shorts usa `audio_segments_short`, centrado na pista, na mudança de plano e na solução em equipe, além de selecionar apenas as cenas desse destaque. Os áudios são distintos. A duração final é verificada por ffprobe, Mutagen ou metadados lidos pelo FFmpeg portátil. Se ficar fora da faixa, o job é marcado como falha.

## Produção recorrente automática

Quando o usuário ativa o calendário de produção:
- O agendador escolhe o próximo planeta não utilizado.
- Gera e persiste a história completa e o storyboard.
- Só depois inicia a renderização dos formatos selecionados.
- Mantém o episódio aguardando revisão editorial após a renderização.

A publicação automática não é ligada por padrão. O upload/agendamento no YouTube depende da autorização OAuth do canal e da aprovação do episódio.

## Continuidade visual

- Luna: uniforme magenta/roxo, óculos rosa e estrela dourada.
- Tomi: uniforme azul/amarelo, pulseira luminosa e estrela dourada.
- Pipo: cão caramelo, orelhas caídas e colete azul.
- Manter modelos, cores, proporções, acessórios e emblemas.
- Variar bioma, habitantes, arquitetura, cores do cenário e props conforme o planeta.
- Não imitar personagens ou franquias existentes.

## Estado do motor

O motor atual usa desenho procedural com Pillow e FFmpeg. No ICP, usa Edge TTS com vozes brasileiras separadas para narrador, Luna e Tomi, e voz de pitch elevado para Pipo; fora do ICP, pode usar espeak-ng com variações de pitch. O movimento é procedural e ainda não há sincronização labial quadro a quadro nem rigging 2D profissional.
