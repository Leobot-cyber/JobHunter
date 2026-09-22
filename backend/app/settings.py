from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
SETTINGS_PATH = DATA_DIR / "settings.json"


class ModelSettings(BaseModel):
    provider: str = "openai_compat"
    base_url: str = "https://api.deepseek.com/v1"
    api_key: str = ""
    model: str = "deepseek-chat"
    temperature: float = 0.2
    sources: list[str] = Field(
        default_factory=lambda: ["remotive", "remoteok", "arbeitnow", "themuse"]
    )


class EnvSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_prefix="JOBHUNTER_",
        extra="ignore",
    )
    provider: str = "openai_compat"
    base_url: str = "https://api.deepseek.com/v1"
    api_key: str = ""
    model: str = "deepseek-chat"
    temperature: float = 0.2


def default_settings() -> ModelSettings:
    env = EnvSettings()
    return ModelSettings(
        provider=env.provider,
        base_url=env.base_url,
        api_key=env.api_key,
        model=env.model,
        temperature=env.temperature,
    )


def load_settings() -> ModelSettings:
    if SETTINGS_PATH.exists():
        return ModelSettings.model_validate_json(SETTINGS_PATH.read_text())
    settings = default_settings()
    save_settings(settings)
    return settings


def save_settings(settings: ModelSettings) -> None:
    SETTINGS_PATH.write_text(settings.model_dump_json(indent=2))
