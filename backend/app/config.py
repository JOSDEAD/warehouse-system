from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    supabase_url: str
    supabase_key: str
    slack_bot_token: str
    slack_app_token: str  # for Socket Mode
    slack_signing_secret: str
    slack_notify_channel: str = "#bodega"
    audio_daemon_secret: str = "change-this-secret"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()
