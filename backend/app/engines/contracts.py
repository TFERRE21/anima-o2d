"""Stable data contracts between independent production engines."""
from dataclasses import dataclass,field
from typing import Any
@dataclass(frozen=True)
class CharacterCue:
    character_id:str
    action:str="idle"
    expression:str="neutral"
    viseme:str="rest"
    speaking:bool=False
@dataclass(frozen=True)
class SceneBeat:
    scene_id:str
    environment_id:str
    start:float
    end:float
    action:str
    characters:tuple[CharacterCue,...]=()
@dataclass
class EpisodeJob:
    episode_id:str
    title:str
    beats:list[SceneBeat]
    audio_timeline:list[dict[str,Any]]=field(default_factory=list)
    render_engine:str="blender-rx580"
    def validate(self):
        if not self.episode_id or not self.title or not self.beats: raise ValueError("Episódio incompleto.")
        previous=0.0
        for beat in self.beats:
            if beat.start<previous or beat.end<=beat.start: raise ValueError("Timeline de cenas inválida.")
            previous=beat.end
