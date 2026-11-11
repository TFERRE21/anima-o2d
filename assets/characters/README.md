# Biblioteca 3D reutilizável — Luna, Tomi e Pipo

Esta etapa cria os modelos iniciais no computador Windows que possui Blender e RX 580. Ela não exige novo deploy da VPS nem reinstalação de bpy.

## Gerar os arquivos

Na raiz do repositório, com Blender 5.x instalado:

```powershell
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background --python tools\build_character_assets.py
```

O script gera:

- `assets/characters/luna/luna.blend` e `luna.glb`
- `assets/characters/tomi/tomi.blend` e `tomi.glb`
- `assets/characters/pipo/pipo.blend` e `pipo.glb`
- Um `manifest.json` por personagem com versão, arquivo e nomes dos controles.

## Convenções

- Cada personagem tem um ID versionado e um armature próprio.
- Luna e Tomi têm controles de tronco, cabeça, mandíbula, braços, mãos, pernas e pés.
- Pipo tem controles quadrúpedes, mandíbula, orelhas e cauda.
- Os materiais e nomes das peças usam identificadores estáveis para facilitar atualizações.
- Os arquivos .blend são os mestres editáveis; GLB é a exportação para visualização e integração.

## Importante sobre a etapa

Estes são modelos-base estilizados com peças separadas e armaduras de partida, não modelos finais aprovados para produção. A próxima revisão visual deve conferir proporções, silhuetas, articulações, deformação e aparência em poses de frente, perfil e 3/4 no Blender RX580. Só depois dessa aprovação os assets devem ser marcados como versão final e conectados ao motor de episódios.
