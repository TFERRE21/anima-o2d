"""Original planet adventures for Pequenos Guardiões."""
WORLDS = [
 {"planet":"Aurora-7","biome":"crystal forests","colors":["#172a62","#5bd7d0","#a4f4dc"],"challenge":"the crystal river has stopped flowing","value":"cooperação","solution":"Luna maps the safe path, Tomi organizes a team and Pipo discovers a blocked crystal gate; they reopen the river together"},
 {"planet":"Vermelhão","biome":"red canyons","colors":["#542d55","#ff9b68","#ffd18a"],"challenge":"a dust storm has hidden the town's solar markers","value":"responsabilidade","solution":"the friends place bright markers with the local helpers and guide everyone to the safe shelter"},
 {"planet":"Oceânia Azul","biome":"underwater domes","colors":["#073b63","#39c9df","#9cf4ed"],"challenge":"little sea creatures are confused by floating litter","value":"cuidado com a natureza","solution":"they sort the litter with the ocean guardians and keep the habitat clean without disturbing wildlife"},
 {"planet":"Flora-Lume","biome":"giant glowing gardens","colors":["#244b48","#a6df76","#f3e79b"],"challenge":"the glowing flowers are losing their light","value":"cuidado e paciência","solution":"they learn the flowers need clean water and shade, then restore the garden with the botanists"},
 {"planet":"Nuvem Doce","biome":"floating cloud islands","colors":["#5966a7","#e4c9ff","#fff0c8"],"challenge":"the bridges between cloud islands are out of alignment","value":"confiança e trabalho em equipe","solution":"they listen to each island's residents and reconnect the bridges with a safe teamwork plan"},
 {"planet":"Gelus-9","biome":"ice caves and auroras","colors":["#183e69","#8ee8ff","#d8f7ff"],"challenge":"a baby snow-beast is separated from its family","value":"empatia","solution":"they stay at a safe distance, calm the frightened creature and contact the planet's wildlife rangers"},
 {"planet":"Vulcânia Verde","biome":"warm volcanic valleys","colors":["#46314d","#ff9b55","#b9e58c"],"challenge":"the village's cooling garden has dried out","value":"solidariedade","solution":"they help the villagers repair water channels with adult supervision and share the water fairly"},
 {"planet":"Anel de Safira","biome":"ring-shaped moon bases","colors":["#263b70","#9fb9ff","#f7d78b"],"challenge":"the station's navigation lights are blinking in the wrong order","value":"pensamento crítico","solution":"they compare clues, find a harmless wiring mix-up and ask the station engineer to fix it"},
 {"planet":"Pétala-3","biome":"giant flower fields","colors":["#5c3970","#ffb8d8","#f8e7a5"],"challenge":"the pollinator robots cannot find the flower paths","value":"respeito às diferenças","solution":"they design colorful signs that help every little helper find a route that suits them"},
 {"planet":"Eco-Lua","biome":"quiet lunar valleys","colors":["#303b62","#c1c9e8","#f5e9b5"],"challenge":"the community's message beacon has gone silent","value":"honestidade","solution":"they admit a small mistake in the setup, correct it together and restore the beacon"}
]

def episode_for_world(world):
    planet = world["planet"]
    challenge = world["challenge"]
    value = world["value"]
    solution = world["solution"]
    title = f"A Missão em {planet}"
    story = (
      f"Os Pequenos Guardiões Luna, Tomi e Pipo viajam na nave Estrelinha até {planet}, "
      f"um planeta de {world['biome']}. Ao chegar, descobrem que {challenge}. "
      f"Luna observa as pistas com seu kit de inventora. Tomi conversa com os moradores e organiza um plano seguro. "
      f"Pipo percebe um detalhe importante e ajuda os amigos. Juntos, com a ajuda dos habitantes e dos adultos responsáveis, "
      f"{solution}. Ninguém enfrenta perigos sozinho: os amigos pedem ajuda, respeitam os seres daquele planeta e trabalham em equipe. "
      f"No final, todos celebram aprendendo sobre {value}. A frase da missão é: Primeiro pensamos, depois ajudamos!"
    )
    return title, story
