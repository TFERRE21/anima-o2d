from backend.app.character_profiles import CHARACTER_PROFILES,validate_character_library
class CharacterEngine:
    engine_id="characters-v1"
    def list_characters(self): return [{"name":k,**v} for k,v in CHARACTER_PROFILES.items()]
    def validate(self): return validate_character_library()
