from backend.app.character_profiles import CHARACTER_PROFILES, validate_character_library


class CharacterEngine:
    """Canonical cast registry consumed by the 2D artwork and episode pipeline."""

    engine_id = "characters-v2-visual-bible"
    design_revision = "pequenos-guardioes-art-direction-2026-11"

    def list_characters(self):
        return [
            {"name": name, **profile, "design_revision": self.design_revision}
            for name, profile in CHARACTER_PROFILES.items()
        ]

    def get_character(self, name: str):
        key = next((item for item in CHARACTER_PROFILES if item.casefold() == str(name).casefold()), None)
        if key is None:
            raise KeyError(f"Personagem não cadastrado: {name}")
        return {"name": key, **CHARACTER_PROFILES[key], "design_revision": self.design_revision}

    def validate(self):
        result = validate_character_library()
        result["engine"] = self.engine_id
        result["design_revision"] = self.design_revision
        result["visual_identity_complete"] = all(
            bool(profile.get("visual_identity", {}).get("signature_colors"))
            for profile in CHARACTER_PROFILES.values()
        )
        result["ok"] = bool(result["ok"] and result["visual_identity_complete"])
        return result
