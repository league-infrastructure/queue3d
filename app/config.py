from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Queue3D"
    SECRET_KEY: str = "change-me-in-production"
    DEBUG: bool = False

    DATABASE_URL: str = "sqlite:///data/queue3d.db"

    UPLOAD_DIR: Path = Path("data/uploads")
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024  # 50 MB

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""

    EXTERNAL_URL: str = "http://localhost:8000"

    # extra="ignore" so dotconfig's generated .env (which includes metadata
    # like _VERSION) loads cleanly without tripping pydantic's extra-fields guard.
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
