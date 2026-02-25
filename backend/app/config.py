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

    # Persistent storage base path for generated images (DEC-002)
    # Override via STORAGE_PATH env var; defaults to ./storage next to the DB.
    storage_path: str = "./storage"

    # Email notification (DEC-007)
    # Use a Gmail App Password (not the account password).
    # Generate at: https://myaccount.google.com/apppasswords
    smtp_from_email: str = ""
    smtp_app_password: str = ""

    model_config = {"env_file": ".env"}


settings = Settings()
