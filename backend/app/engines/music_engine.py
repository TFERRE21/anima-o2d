MOODS={"adventure","curiosity","mystery","tender","celebration","calm"}
class MusicEngine:
    engine_id="music-v1"
    def cue(self,mood,start,end,effects=None):
        if mood not in MOODS or start<0 or end<=start: raise ValueError("Cue musical inválido.")
        return {"mood":mood,"start":start,"end":end,"effects":effects or []}
