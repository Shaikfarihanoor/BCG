from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings and configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "Bulk Certificate Generator API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "sqlite:///./certificates.db"

    # Storage settings
    STORAGE_DIR: str = "./generated"

    # Business logic limits
    MAX_RECIPIENTS_PER_JOB: int = 1000
    FLAG_DUPLICATE_EMAILS: bool = True
    MAX_NAME_LENGTH: int = 120

    # Pagination limits
    DEFAULT_PAGE_SIZE: int = 50
    MAX_PAGE_SIZE: int = 500

    @property
    def storage_path(self) -> Path:
        """Return resolved Path to the storage directory."""
        path = Path(self.STORAGE_DIR).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()
