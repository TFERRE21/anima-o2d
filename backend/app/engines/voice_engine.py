class VoiceEngine:
    engine_id="voice-v1"
    def speaker_at(self,timeline,seconds):
        return next((str(x["speaker"]) for x in timeline if float(x.get("start",0))<=seconds<float(x.get("end",0))),None)
    def validate(self,timeline):
        last=0.0
        for cue in sorted(timeline,key=lambda x:float(x.get("start",0))):
            start,end=float(cue.get("start",0)),float(cue.get("end",0))
            if start<last or end<=start or not cue.get("speaker"): raise ValueError("Timeline de voz inválida.")
            last=end
