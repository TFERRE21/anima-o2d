class CompositionEngine:
    engine_id="composition-v1"
    def shot(self,framing,move,start,end):
        if framing not in {"wide","medium","closeup","over_shoulder","portrait"}: raise ValueError("Enquadramento inválido.")
        if move not in {"static","pan","dolly_in","dolly_out","tracking","orbit"} or start<0 or end<=start: raise ValueError("Plano inválido.")
        return {"framing":framing,"move":move,"start":start,"end":end}
