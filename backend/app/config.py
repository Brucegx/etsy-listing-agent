from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/auth/callback"

    # API Keys (passed through to LangGraph engine)
    anthropic_api_key: str = ""
    minimax_api_key: str = ""
    gemini_api_key: str = ""

    # Database
    database_url: str = "sqlite+aiosqlite:///./etsy_agent.db"

    # Frontend
    frontend_url: str = "http://localhost:3000"

    # Session secret (required: set via SESSION_SECRET env var)
    session_secret: str = ""

    model_config = {"env_file": ".env"}


settings = Settings()
