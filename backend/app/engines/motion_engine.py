ACTIONS={"idle","talk","converse","walk","run","jump","point","discover","sniff","work","write","surprise","celebrate","listen","wave"}
EXPRESSIONS={"neutral","happy","curious","surprised","sad","worried","thinking","excited"}
class MotionEngine:
    engine_id="motion-v1"
    def validate_cue(self,action,expression="neutral"):
        if action not in ACTIONS or expression not in EXPRESSIONS: raise ValueError("Cue de animação inválido.")
        return {"action":action,"expression":expression}
