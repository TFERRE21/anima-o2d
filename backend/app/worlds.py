"""Deterministic story studio for original interplanetary children's adventures.

Every generated episode gets a never-reused planet identifier, a distinct mission
combination, a 15-scene story, a long-form narration and a separate Shorts narration.
"""
from __future__ import annotations

WORLDS = [
    {"planet":"Aurora-7","biome":"florestas de cristais luminosos","palette":"aurora","inhabitants":"Lumins, pequenos seres de luz que cuidam dos cristais","landmark":"o Grande Bosque de Cristal"},
    {"planet":"Vermelhão","biome":"cânions vermelhos e desertos de areia dourada","palette":"red","inhabitants":"Rochins, simpáticos construtores de pontes","landmark":"o Vale dos Ventos"},
    {"planet":"Oceânia Azul","biome":"oceanos brilhantes e cidades sob redomas","palette":"ocean","inhabitants":"Neris, pequenos guardiões do mar","landmark":"a Praça das Conchas"},
    {"planet":"Flora-Lume","biome":"jardins gigantes e flores que brilham à noite","palette":"flora","inhabitants":"Florins, jardineiros de antenas coloridas","landmark":"o Jardim das Mil Cores"},
    {"planet":"Nuvem Doce","biome":"ilhas flutuantes e pontes de arco-íris","palette":"cloud","inhabitants":"Nuvins, moradores que viajam em pequenos planadores","landmark":"a Ponte dos Ventos"},
    {"planet":"Gelus-9","biome":"montanhas de gelo azul e auroras dançantes","palette":"ice","inhabitants":"Glacis, criaturas gentis que protegem os animais polares","landmark":"a Gruta da Aurora"},
    {"planet":"Vulcânia Verde","biome":"vales vulcânicos mornos e florestas resistentes","palette":"volcano","inhabitants":"Vulcânicos, inventores de jardins térmicos","landmark":"o Vale das Fontes"},
    {"planet":"Anel de Safira","biome":"estações em luas pequenas cercadas por anéis brilhantes","palette":"sapphire","inhabitants":"Safirins, técnicos que cuidam das estações espaciais","landmark":"a Estação das Três Luas"},
    {"planet":"Pétala-3","biome":"campos de flores enormes e trilhas perfumadas","palette":"petal","inhabitants":"Pétalis, pequenos robôs polinizadores e seus cuidadores","landmark":"o Campo das Pétalas"},
    {"planet":"Eco-Lua","biome":"vales lunares silenciosos e lagos espelhados","palette":"moon","inhabitants":"Ecos, moradores que guardam histórias e mensagens","landmark":"o Farol das Memórias"},
]

MISSIONS = [
    {"problem":"o farol comunitário parou de enviar mensagens","clue":"três sinais luminosos piscam fora de ordem","solution":"organizam as pistas, encontram uma ligação trocada e chamam a técnica responsável para ajustar o farol","value":"pensamento cuidadoso e cooperação","object":"farol"},
    {"problem":"as sementes do jardim comunitário foram levadas pelo vento","clue":"pequenas marcas no solo mostram onde as sementes pousaram","solution":"criam placas coloridas e ajudam os jardineiros a replantar cada semente no lugar certo","value":"cuidado com a natureza","object":"sementes"},
    {"problem":"a ponte de luz que liga duas vilas apagou","clue":"um mapa antigo mostra que falta alinhar dois cristais de sinalização","solution":"ouvem as duas comunidades, alinham as placas com os moradores e reabrem a passagem com segurança","value":"diálogo e trabalho em equipe","object":"ponte"},
    {"problem":"os pequenos animais locais não encontram água fresca","clue":"Pipo percebe pegadas perto de um canal coberto por folhas","solution":"pedem ajuda aos guardiões locais para limpar o canal sem assustar os animais e deixam água em pontos seguros","value":"empatia e respeito aos seres vivos","object":"canal de água"},
    {"problem":"a biblioteca perdeu a ordem dos livros de histórias","clue":"Luna encontra símbolos de cores nas lombadas e Tomi percebe uma sequência","solution":"convidam os moradores a organizar os livros por assunto e criam um sistema simples de etiquetas","value":"organização e colaboração","object":"biblioteca"},
    {"problem":"uma chuva de poeira cobriu as placas que orientam visitantes","clue":"Tomi nota que as estrelas no mapa continuam visíveis","solution":"com os habitantes, desenham placas grandes e resistentes e indicam o caminho até o abrigo comunitário","value":"responsabilidade e prevenção","object":"placas de orientação"},
    {"problem":"o sistema de reciclagem está misturando materiais diferentes","clue":"Luna percebe que as cores dos recipientes foram trocadas","solution":"conferem os símbolos com a equipe local, corrigem as etiquetas e explicam a separação aos moradores","value":"responsabilidade e cuidado coletivo","object":"reciclador"},
    {"problem":"o coral musical do planeta perdeu o ritmo","clue":"Pipo acompanha um som baixinho que vem de uma concha distante","solution":"escutam cada morador, descobrem que um instrumento está desafinado e ajudam a afiná-lo com o músico responsável","value":"escuta, paciência e respeito","object":"coral musical"},
    {"problem":"as luzes do caminho para a escola estão piscando sem padrão","clue":"Tomi registra a sequência e Luna encontra uma peça solta no painel externo","solution":"isolam a área, avisam a professora local e ajudam a equipe técnica a identificar a peça correta","value":"segurança e pedir ajuda","object":"luzes da escola"},
    {"problem":"os recados da comunidade estão chegando às casas erradas","clue":"as etiquetas das caixas de mensagem têm desenhos parecidos","solution":"conversam com os moradores, conferem cada nome com um adulto e criam símbolos mais fáceis de distinguir","value":"honestidade e atenção aos outros","object":"caixas de mensagem"},
    {"problem":"um pequeno robô ajudante ficou sem saber qual tarefa realizar","clue":"Luna descobre que as instruções foram escritas em símbolos que ele não conhece","solution":"perguntam ao criador do robô como ele aprende, traduzem as instruções juntos e atualizam o painel","value":"inclusão e respeito às diferenças","object":"robô ajudante"},
    {"problem":"o observatório não consegue mostrar a constelação favorita das crianças","clue":"Tomi percebe que uma lente está coberta por poeira brilhante","solution":"pedem orientação à astrônoma local, limpam a lente com o equipamento adequado e compartilham o céu com a turma","value":"curiosidade e cooperação","object":"observatório"},
]

TWISTS = [
    "No início, todos pensam que a solução está no maior equipamento, mas a pista mais importante é um detalhe pequeno que quase ninguém percebeu.",
    "Um dos habitantes tem uma ideia diferente da dos outros; quando todos param para escutar, descobrem que as duas ideias podem trabalhar juntas.",
    "A primeira tentativa não funciona, e a equipe aprende que mudar o plano não é fracassar: é observar melhor e tentar com cuidado.",
    "Pipo encontra uma pista inesperada, mas só quando Luna e Tomi juntam suas observações é que conseguem entender o que ela significa.",
    "Os moradores já tinham tentado resolver o problema sozinhos. O que faltava era dividir as tarefas e pedir ajuda a quem conhecia cada parte.",
    "Uma informação parecia verdadeira, mas Tomi confere os sinais antes de espalhá-la. Assim, a equipe evita uma conclusão precipitada.",
]

def _unique_planet(base_name: str, episode_number: int) -> str:
    cycle = episode_number // len(WORLDS)
    if cycle == 0:
        return base_name
    return f"{base_name} {cycle + 1}"

def build_episode_plan(episode_number: int, used_planets: set[str] | None = None) -> dict:
    """Build one fresh, fully structured episode before any video rendering."""
    used_planets = used_planets or set()
    idx = max(0, int(episode_number))
    world = dict(WORLDS[idx % len(WORLDS)])
    planet = _unique_planet(world["planet"], idx)
    suffix = 2
    while planet in used_planets:
        planet = f"{world['planet']} {idx + suffix}"
        suffix += 1
    world["planet"] = planet
    mission = MISSIONS[(idx * 5 + idx // len(WORLDS)) % len(MISSIONS)]
    twist = TWISTS[(idx * 3 + 1) % len(TWISTS)]
    value = mission["value"]
    title = f"A Missão de {planet}"
    scenes = [
        ("A PARTIDA", f"A nave Estrelinha parte para {planet}.", "A tripulação confere o mapa, prepara os cintos e parte em uma viagem segura."),
        ("UM PLANETA NOVO", f"Uma paisagem de {world['biome']} aparece pela janela.", f"Luna, Tomi e Pipo observam {world['landmark']} e descrevem as cores e formas do lugar."),
        ("NOVOS AMIGOS", f"Os Guardiões conhecem os {world['inhabitants']}.", "Os habitantes recebem a equipe e explicam como vivem e o que é importante para sua comunidade."),
        ("A MISSÃO", f"Descobrem que {mission['problem']}.", "Os amigos escutam com atenção antes de sugerir qualquer solução."),
        ("OLHOS DE INVENTORA", f"Luna procura pistas perto de {mission['object']}.", f"Ela encontra um indício: {mission['clue']}."),
        ("PLANO DO TOMI", "Tomi desenha um plano simples e seguro.", "Ele divide as tarefas, pergunta quem pode ajudar e lembra que ninguém deve agir sozinho."),
        ("PIPO PERCEBE", "Pipo fareja, escuta e aponta para um detalhe.", "A pista dele confirma parte das observações e ajuda o grupo a entender o problema."),
        ("UMA SURPRESA", "A primeira ideia precisa de um pequeno ajuste.", twist),
        ("OUVIR TAMBÉM É AJUDAR", "Luna e Tomi pedem a opinião dos moradores.", "Cada pessoa compartilha o que sabe, e o grupo combina as melhores ideias."),
        ("MÃOS À OBRA", "Todos começam a solução em equipe.", mission["solution"].capitalize() + "."),
        ("A COMUNIDADE CONSEGUE", "O planeta volta a sorrir.", "Os habitantes testam a solução, agradecem aos amigos e combinam como cuidar dela no futuro."),
        ("A LIÇÃO DA VIAGEM", f"A aventura ensina {value}.", "Luna e Tomi lembram que ajudar começa por escutar, pensar e trabalhar em equipe."),
    ]
    # 12 distinct narration passages; the production script expands them into a
    # full episode rather than reusing a short summary as the entire voice track.
    long_script = [
        f"Olá, exploradores! Preparem a imaginação, porque os Pequenos Guardiões estão prestes a conhecer um lugar que nunca visitaram. Luna, Tomi e Pipo estão na nave Estrelinha, conferindo o mapa espacial. Luna ajusta seus óculos cor-de-rosa, Tomi verifica a rota e Pipo abana o rabo, animado com a aventura. Hoje, a equipe vai descobrir como uma atitude gentil pode transformar um planeta inteiro.",
        f"A nave atravessa um caminho de estrelas e se aproxima de {planet}. Pela janela, os amigos veem {world['biome']}. Ao longe está {world['landmark']}, um lugar cheio de detalhes que parecem contar histórias. Luna observa as cores e desenha o cenário em seu caderno. Tomi compara o mapa com a paisagem. Pipo encosta o focinho na janela e solta um latido baixinho de encantamento.",
        f"Depois de pousar em uma área segura, os amigos encontram os {world['inhabitants']}. Uma moradora chamada Liri vem recebê-los e explica que aquele lugar é especial para todos. Ela conta como as famílias cuidam umas das outras e como cada pessoa ajuda a comunidade. Luna pergunta o que os moradores mais gostam em seu planeta. Tomi escuta sem interromper. Pipo cumprimenta os novos amigos com alegria.",
        f"Logo os habitantes contam o que está acontecendo: {mission['problem']}. O problema está atrapalhando uma atividade importante para as famílias. Ninguém sabe exatamente como começou, e algumas pessoas estão preocupadas. Luna diz que não adianta adivinhar nem procurar culpados. Primeiro é preciso conhecer os fatos. Tomi concorda e sugere que todos contem o que viram, com calma e respeito.",
        f"Luna abre seu kit de inventora e observa o local com atenção. Ela procura marcas, cores, sons e pequenos sinais que possam explicar a situação. Perto de {mission['object']}, encontra uma pista: {mission['clue']}. Ela registra tudo em seu caderno, sem mexer em equipamentos que precisam de um adulto. A inventora percebe que uma boa investigação começa com paciência e olhos atentos.",
        f"Tomi reúne os amigos e os moradores para montar um plano. Ele desenha um mapa simples, mostra onde cada pessoa pode ajudar e pergunta quem conhece melhor aquela parte do planeta. Uma moradora explica um detalhe que não aparece no mapa. Tomi acrescenta a informação e lembra a todos que segurança vem primeiro. Ninguém precisa correr ou se arriscar. Cada tarefa será feita com a orientação de quem conhece o lugar.",
        f"Enquanto o grupo conversa, Pipo fareja o chão e escuta um som diferente. Ele caminha alguns passos, para e olha para Luna. A equipe se aproxima somente depois de confirmar que o local é seguro. O cão encontrou outra pista que combina com as anotações da inventora. Tomi compara os detalhes e percebe que o problema não era exatamente como todos imaginavam. Ajudar também é prestar atenção ao que os outros descobriram.",
        f"Os amigos fazem uma primeira tentativa, mas ela não resolve tudo. Por um instante, alguns moradores ficam desanimados. Luna respira fundo e diz que uma tentativa que não funciona pode ensinar algo importante. Tomi lembra a equipe da surpresa que descobriram: {twist} Todos voltam a observar o local. Em vez de desistir, ajustam o plano, dividem melhor as tarefas e pedem a orientação de uma especialista da comunidade.",
        f"Agora cada pessoa tem uma função. Uma criança organiza os materiais, os adultos responsáveis verificam os equipamentos e os amigos acompanham as pistas. Luna explica sua ideia com desenhos simples. Tomi pergunta se todos entenderam e convida cada morador a falar. Ninguém é deixado de lado. Pipo acompanha a equipe e comemora quando percebe que todos estão colaborando. As diferenças entre as pessoas se tornam uma força para resolver o desafio.",
        f"Com cuidado e cooperação, o grupo coloca a solução em prática: {mission['solution']}. Luna verifica se as etapas foram seguidas, Tomi combina os sinais para que todos saibam quando cada parte estiver pronta e os moradores fazem a checagem final. A cada pequeno avanço, a comunidade fica mais confiante. A missão mostra que não existe uma única pessoa capaz de fazer tudo sozinha. Quando cada um contribui, o resultado pode ser muito maior.",
        f"Finalmente, a atividade da comunidade pode continuar. Os habitantes observam o resultado, testam se a solução funciona e agradecem aos Pequenos Guardiões. Liri explica que também vai ensinar o que aprendeu aos vizinhos, para que o planeta continue bem cuidado. Luna fica feliz porque sua ideia ajudou. Tomi sorri ao ver todos trabalhando juntos. Pipo recebe carinho dos novos amigos e dá uma voltinha, orgulhoso de sua pequena descoberta.",
        f"Antes de voltar para a nave Estrelinha, Luna e Tomi conversam com as crianças que estão assistindo. Hoje aprendemos sobre {value}. Também descobrimos que é importante ouvir, conferir as informações, respeitar os moradores e pedir ajuda quando uma tarefa exige experiência. Luna lembra: Uma boa ideia pode mudar tudo! Tomi completa: Primeiro pensamos, depois ajudamos! E Pipo late como quem diz que a amizade deixa qualquer viagem mais bonita.",
        f"A equipe olha mais uma vez para {planet} e se despede. Um novo destino já aparece no mapa, mas cada planeta tem sua própria história e merece ser conhecido com respeito. Os Pequenos Guardiões não chegam para mandar: chegam para aprender junto com os habitantes e colaborar. E você também pode ser um guardião do bem na sua escola, na sua casa e na sua comunidade. Até a próxima aventura, exploradores!"
    ]
    # Expand to a measured long-form voice track with unique beats, not copy-paste loops.
    long_script += [
        f"Na nave, os amigos registram no diário da missão o que funcionou e o que fariam de outro jeito. Luna desenha a pista principal, Tomi anota como a equipe se organizou e Pipo deixa uma marca de patinha na última página. O diário ajuda a lembrar que cada aventura ensina algo novo. Mesmo quando os planetas são muito diferentes, o respeito, a amizade e a vontade de ajudar podem aproximar todos.",
        f"Durante a viagem de volta, os amigos imaginam como os moradores continuarão cuidando de {world['landmark']}. Eles sabem que uma solução só é boa quando a comunidade consegue mantê-la. Por isso, não fizeram tudo pelos habitantes: compartilharam ideias, escutaram quem conhecia o lugar e ajudaram a construir um plano que todos podem usar. Essa é uma das maiores lições da viagem: ajudar também significa ensinar e aprender juntos.",
        f"E agora fica uma pergunta para você: qual atitude poderia melhorar o lugar onde você vive? Talvez organizar um espaço que todos usam, escutar um amigo, cuidar de uma planta ou pedir ajuda a um adulto quando algo parecer perigoso. Pequenas atitudes podem criar grandes mudanças. Os Pequenos Guardiões acreditam que cada pessoa pode fazer parte da solução quando age com cuidado, coragem e bondade."
    ]
    dialogues = [
        {"scene": 0, "speaker": "Luna", "text": f"Tomi, confira os cintos! Quero que nossa chegada a {planet} seja tranquila."},
        {"scene": 0, "speaker": "Tomi", "text": "Tudo certo, Luna. Rota confirmada. Pipo, preparado para conhecer novos amigos?"},
        {"scene": 1, "speaker": "Pipo", "text": "Au! Au! Eu vi luzes brilhando lá embaixo!"},
        {"scene": 2, "speaker": "Luna", "text": "Olá! Somos os Pequenos Guardiões. Queremos conhecer vocês e entender como podemos ajudar."},
        {"scene": 2, "speaker": "Tomi", "text": "Podem contar o que aconteceu. Vamos ouvir com atenção, sem tirar conclusões antes da hora."},
        {"scene": 3, "speaker": "Luna", "text": f"Então o desafio é este: {mission['problem']}. Vamos descobrir o que está acontecendo."},
        {"scene": 3, "speaker": "Tomi", "text": "Cada detalhe importa. Primeiro vamos conversar com os moradores e observar o lugar com segurança."},
        {"scene": 4, "speaker": "Luna", "text": f"Encontrei uma pista perto de {mission['object']}: {mission['clue']}. Vou registrar no meu caderno!"},
        {"scene": 5, "speaker": "Tomi", "text": "Minha proposta é dividir as tarefas. Quem conhece melhor esta área pode orientar cada passo."},
        {"scene": 6, "speaker": "Pipo", "text": "Au! Au! Esperem! Tem mais uma pista aqui perto!"},
        {"scene": 6, "speaker": "Luna", "text": "Muito bem, Pipo! Sua descoberta combina com as minhas anotações."},
        {"scene": 7, "speaker": "Tomi", "text": "A primeira tentativa não resolveu tudo, mas agora sabemos mais. Vamos ajustar o plano juntos."},
        {"scene": 8, "speaker": "Luna", "text": "Moradores, o que vocês acham desta ideia? Queremos ouvir quem conhece este planeta."},
        {"scene": 8, "speaker": "Tomi", "text": "Quando cada pessoa participa, encontramos soluções mais cuidadosas e ninguém fica de fora."},
        {"scene": 9, "speaker": "Luna", "text": "Agora sim! Vamos seguir as etapas com calma e conferir cada detalhe."},
        {"scene": 9, "speaker": "Tomi", "text": "Equipe pronta? Moradores orientando? Então vamos trabalhar juntos!"},
        {"scene": 10, "speaker": "Pipo", "text": "Au! Au! Conseguimos! Todo mundo ajudou!"},
        {"scene": 10, "speaker": "Luna", "text": "Conseguimos porque juntamos nossas ideias e respeitamos a experiência dos moradores."},
        {"scene": 11, "speaker": "Tomi", "text": f"Hoje aprendemos sobre {value}. Pensar, escutar e pedir ajuda também são atitudes de coragem."},
        {"scene": 11, "speaker": "Luna", "text": "E lembre-se: uma boa ideia pode mudar tudo quando é colocada em prática com carinho!"},
    ]
    dialogue_by_scene = {}
    for line in dialogues:
        dialogue_by_scene.setdefault(line["scene"], []).append(line)
    # Keep the long episode conversational: six narrative chapters alternate
    # with character dialogue so the heroes are heard, not merely described.
    audio_segments_long = []
    for block in range(6):
        first = block * 2
        narrator_text = " ".join(long_script[first:first + 2])
        audio_segments_long.append({"speaker": "Narrador", "text": narrator_text, "scene": first})
        for scene_index in (first, first + 1):
            audio_segments_long.extend(dialogue_by_scene.get(scene_index, []))

    # Shorts use the most emotional section: the unexpected clue, the failed
    # first attempt, the team's decision to listen, and the successful solution.
    short_segments = [
        {"speaker": "Narrador", "text": f"Na parte mais difícil da missão em {planet}, a primeira tentativa falhou. O problema parecia maior do que todos imaginavam: {mission['problem']}.", "scene": 7},
        {"speaker": "Luna", "text": f"Esperem! A pista que encontrei perto de {mission['object']} mostra outro caminho: {mission['clue']}.", "scene": 7},
        {"speaker": "Tomi", "text": "Então vamos mudar o plano. Primeiro ouvimos os moradores, depois dividimos as tarefas e conferimos tudo com segurança.", "scene": 8},
        {"speaker": "Pipo", "text": "Au! Au! Eu também encontrei uma pista! Olhem aqui!", "scene": 8},
        {"speaker": "Luna", "text": f"Agora entendi! Se trabalharmos juntos, podemos {mission['solution']}.", "scene": 9},
        {"speaker": "Tomi", "text": "Equipe e moradores, cada um na sua tarefa. Vamos fazer isso juntos!", "scene": 9},
        {"speaker": "Narrador", "text": f"Com diálogo e cooperação, a comunidade consegue resolver o desafio. A aventura ensina {value}.", "scene": 10},
        {"speaker": "Luna", "text": "Uma boa ideia pode mudar tudo! E você, que atitude pode melhorar o lugar onde vive?", "scene": 11},
    ]
    long_dialogue_script = " ".join(f"{line['speaker']}: {line['text']}" for line in dialogues)
    short_script = " ".join(line["text"] for line in short_segments)
    long_audio_words = sum(len(item["text"].split()) for item in audio_segments_long)
    short_audio_words = sum(len(item["text"].split()) for item in short_segments)
    return {
        "title": title, "planet": planet, "biome": world["biome"], "palette": world["palette"],
        "value": value, "challenge": mission["problem"], "synopsis": f"Em {planet}, os amigos ajudam os habitantes a resolver um desafio e aprendem sobre {value}.",
        "story": " ".join(long_script) + " " + long_dialogue_script,
        "long_script": " ".join(long_script), "dialogues": dialogues,
        "dialogue_script": long_dialogue_script,
        "audio_segments_long": audio_segments_long, "audio_segments_short": short_segments,
        "short_script": short_script, "short_highlight": "a pista inesperada, a mudança de plano e a solução em equipe",
        "short_scene_indices": [6, 7, 8, 9, 10, 11],
        "scenes": [
            {"title": item[0], "caption": item[1], "visual_action": item[2]} for item in scenes
        ],
        "characters": ["Luna", "Tomi", "Pipo"], "episode": "planet-journey",
        "word_count_long": long_audio_words,
        "word_count_short": short_audio_words,
        "duration_targets": {
            "16:9": {"min_seconds": 301, "max_seconds": 599, "target_seconds": 420},
            "9:16": {"min_seconds": 60, "max_seconds": 90, "target_seconds": 75},
        },
    }
