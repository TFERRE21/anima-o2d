from backend.app.character_profiles import validate_character_library
from backend.app.engines.orchestrator import EpisodeOrchestrator
from backend.app.engines.contracts import CharacterCue, EpisodeJob, SceneBeat


def test_canonical_character_library_has_three_stable_identities():
    result = validate_character_library()
    assert result["ok"] is True
    assert result["characters"] == ["Luna", "Pipo", "Tomi"]


def test_orchestrator_reports_separate_engines_and_blender_worker():
    result = EpisodeOrchestrator().health()
    assert result["engines"]["characters"]["ok"] is True
    assert result["engines"]["render"] == "blender-rx580"
    assert result["engines"]["voice"] == "voice-v1"
    assert result["engines"]["music"] == "music-v1"


def test_episode_job_accepts_ordered_scene_beats():
    job = EpisodeJob(
        episode_id="test-001",
        title="Teste",
        beats=[
            SceneBeat("scene-1", "aurora", 0, 5, "talk",
                      (CharacterCue("Luna", action="talk", speaking=True),)),
            SceneBeat("scene-2", "aurora", 5, 10, "walk"),
        ],
    )
    job.validate()
