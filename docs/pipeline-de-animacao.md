# Pipeline de produção 2D

## Objetivo

Produzir uma história uma vez e gerar duas montagens finais independentes: 16:9 (1920×1080) e 9:16 (1080×1920).

## Etapas

1. **Roteiro:** criar logline, valor educativo, diálogos e cenas com duração.
2. **Bíblia visual:** anexar referências aprovadas de Luna, Tomi e Pipo; reutilizar os mesmos descritores e imagens de referência.
3. **Storyboard:** definir ação, enquadramento, cenário, falas e duração por cena.
4. **Assets:** criar fundos, personagens em camadas, expressões e poses. Preferir arte 2D vetorial/recortada para reutilizar e animar.
5. **Animação:** rig 2D, keyframes, movimentos de câmera e sincronização labial quando disponível.
6. **Áudio:** narração em português brasileiro, vozes consistentes, trilha licenciada e efeitos discretos.
7. **Composição:** montar timeline, legendas e transições.
8. **Render duplo:** composições próprias para horizontal e vertical.
9. **Controle de qualidade:** validar duração, áudio, legibilidade, áreas seguras, continuidade de personagens e conteúdo apropriado para crianças.
10. **Publicação:** gerar título, descrição, miniatura e metadados; enviar somente após autorização OAuth e revisão do usuário.

## Especificações de saída

| Perfil | Resolução | Uso |
|---|---:|---|
| landscape | 1920×1080 | YouTube tradicional |
| portrait | 1080×1920 | YouTube Shorts |

## Regras técnicas

- Usar dimensões pares e H.264/AAC em MP4.
- Manter taxa de quadros consistente no projeto (ex.: 24 fps).
- Gerar uma timeline lógica comum e duas composições, com posições, escala e legendas próprias.
- Guardar assets, versões de roteiro, jobs e logs por projeto.
- Não publicar automaticamente enquanto o usuário não habilitar explicitamente a opção e conectar o canal.
- Não usar imagens, músicas, vozes ou personagens de terceiros sem direitos adequados.

## Estado atual

A aplicação no repositório contém apenas a estrutura inicial de API e interface. A geração de cenas, rigging/animação, sincronização labial, fila de renderização e integração OAuth ainda precisam ser implementadas e testadas. Este documento define o desenho funcional para essas próximas etapas.


## Motor visual — etapa planetária

O renderizador procedural agora recebe o planeta do episódio e compõe fundos espaciais, planetas com anéis, luas, paisagens, cristais, construções e elementos da missão com paletas diferentes por mundo. Luna, Tomi e Pipo reutilizam os mesmos desenhos-base em todas as cenas; um pequeno habitante alienígena e a nave Estrelinha reforçam a identidade espacial. Há movimentos contínuos de balanço, cauda, braços, foguete, estrelas e elementos ambientais.

A narração local usa português brasileiro via espeak-ng com velocidade mais pausada e tratamento de loudness/filtros no FFmpeg. Isso melhora a inteligibilidade, mas ainda não equivale a vozes neurais profissionais ou sincronização labial. O motor permanece procedural: ainda não é rigging 2D avançado nem geração de cenas por modelo de vídeo.
