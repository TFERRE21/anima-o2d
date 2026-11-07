from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"

class Settings(BaseSettings):
    app_name: str = "Anima 2D"
    video_provider: str = "none"
    video_provider_api_key: str = ""
    youtube_client_id: str = ""
    youtube_client_secret: str = ""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ProjectRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    story: str = Field(min_length=10, max_length=12000)
    style: str = "2d_cartoon"
    formats: list[str] = ["16:9", "9:16"]

@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.app_name, "version": "0.1.0"}

@app.get("/api/config")
def config():
    return {
        "formats": [
            {"id": "16:9", "width": 1920, "height": 1080, "label": "YouTube horizontal"},
            {"id": "9:16", "width": 1080, "height": 1920, "label": "YouTube Shorts"},
        ],
        "video_provider_configured": bool(settings.video_provider_api_key),
        "youtube_oauth_configured": bool(settings.youtube_client_id and settings.youtube_client_secret),
        "generation_enabled": settings.video_provider != "none" and bool(settings.video_provider_api_key),
    }

@app.post("/api/projects/validate")
def validate_project(payload: ProjectRequest):
    allowed = {"16:9", "9:16"}
    invalid = [item for item in payload.formats if item not in allowed]
    if invalid:
        return {"valid": False, "error": f"Formatos inválidos: {', '.join(invalid)}"}
    if not payload.formats:
        return {"valid": False, "error": "Selecione pelo menos um formato."}
    return {
        "valid": True,
        "project": payload.model_dump(),
        "message": "Projeto validado. O próximo passo é conectar o motor de geração 2D.",
    }

if WEB.exists():
    app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
