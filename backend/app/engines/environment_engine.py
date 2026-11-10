BIOMES={"aurora","red","ocean","flora","cloud","ice","volcano","sapphire","petal","moon"}
class EnvironmentEngine:
    engine_id="environment-v1"
    def validate(self,world):
        palette=str(world.get("palette","aurora")).lower()
        if palette not in BIOMES or not world.get("planet") or not world.get("biome"): raise ValueError("Configuração de mundo inválida.")
        return {"planet":world["planet"],"biome":world["biome"],"palette":palette}
