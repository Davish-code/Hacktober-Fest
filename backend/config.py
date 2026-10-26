import os
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        load_dotenv(dotenv_path=env_file)
except Exception:
    pass

BASE_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = BASE_DIR / "workspace"
WORKSPACE_RUNS_DIR = BASE_DIR / "workspace_runs"
SEED_DIR = BASE_DIR / "workspace_seed"

DEFAULT_ALLOWED_ORIGINS = "http://localhost:3000,http://localhost:5500,http://127.0.0.1:5500"

try:
    # pyrefly: ignore[missing-import]
    from pydantic_settings import BaseSettings

    class Settings(BaseSettings):
        ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
        LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
        PORT: int = int(os.getenv("PORT", "8000"))
        HOST: str = os.getenv("HOST", "0.0.0.0")
        ALLOWED_ORIGINS: str = os.getenv("ALLOWED_ORIGINS", DEFAULT_ALLOWED_ORIGINS)

        # API Keys
        GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")
        GROQ_API_KEY: Optional[str] = os.getenv("GROQ_API_KEY")
        CEREBRAS_API_KEY: Optional[str] = os.getenv("CEREBRAS_API_KEY")

        # Routing Configuration
        DEFAULT_PLANNER_PROVIDER: str = os.getenv("DEFAULT_PLANNER_PROVIDER", "gemini")
        FALLBACK_PLANNER_PROVIDER: str = os.getenv("FALLBACK_PLANNER_PROVIDER", "groq")
        CRITIC_PROVIDER: str = os.getenv("CRITIC_PROVIDER", "groq")

        # Rate Limiting & Quotas
        MAX_REQUESTS_PER_MINUTE: int = int(os.getenv("MAX_REQUESTS_PER_MINUTE", "60"))
        DAILY_TOKEN_QUOTA: int = int(os.getenv("DAILY_TOKEN_QUOTA", "1000000"))

        # Mode Flags
        MOCK_LLM_MODE: bool = os.getenv("MOCK_LLM_MODE", "false").lower() in ("true", "1")
        ENABLE_CIRCUIT_BREAKER: bool = os.getenv("ENABLE_CIRCUIT_BREAKER", "true").lower() in ("true", "1")
        ENABLE_CACHE: bool = os.getenv("ENABLE_CACHE", "true").lower() in ("true", "1")

        # Paths
        BASE_DIR: Path = BASE_DIR
        WORKSPACE_PATH: Path = WORKSPACE_DIR
        WORKSPACE_RUNS_PATH: Path = WORKSPACE_RUNS_DIR
        SEED_PATH: Path = SEED_DIR

        class Config:
            env_file = ".env"
            env_file_encoding = "utf-8"
            extra = "ignore"

    settings = Settings()

except ImportError:
    class FallbackSettings:
        ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
        LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
        PORT: int = int(os.getenv("PORT", "8000"))
        HOST: str = os.getenv("HOST", "0.0.0.0")
        ALLOWED_ORIGINS: str = os.getenv("ALLOWED_ORIGINS", DEFAULT_ALLOWED_ORIGINS)

        GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")
        GROQ_API_KEY: Optional[str] = os.getenv("GROQ_API_KEY")
        CEREBRAS_API_KEY: Optional[str] = os.getenv("CEREBRAS_API_KEY")

        DEFAULT_PLANNER_PROVIDER: str = os.getenv("DEFAULT_PLANNER_PROVIDER", "gemini")
        FALLBACK_PLANNER_PROVIDER: str = os.getenv("FALLBACK_PLANNER_PROVIDER", "groq")
        CRITIC_PROVIDER: str = os.getenv("CRITIC_PROVIDER", "groq")

        MAX_REQUESTS_PER_MINUTE: int = int(os.getenv("MAX_REQUESTS_PER_MINUTE", "60"))
        DAILY_TOKEN_QUOTA: int = int(os.getenv("DAILY_TOKEN_QUOTA", "1000000"))

        MOCK_LLM_MODE: bool = os.getenv("MOCK_LLM_MODE", "false").lower() in ("true", "1")
        ENABLE_CIRCUIT_BREAKER: bool = os.getenv("ENABLE_CIRCUIT_BREAKER", "true").lower() in ("true", "1")
        ENABLE_CACHE: bool = os.getenv("ENABLE_CACHE", "true").lower() in ("true", "1")

        BASE_DIR: Path = BASE_DIR
        WORKSPACE_PATH: Path = WORKSPACE_DIR
        WORKSPACE_RUNS_PATH: Path = WORKSPACE_RUNS_DIR
        SEED_PATH: Path = SEED_DIR

    settings = FallbackSettings()
