from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    This class validates that all required environment variables exist
    and are the correct type when the application starts.
    If a variable is missing, the app crashes immediately (fail-fast).
    """
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore"  # Ignore env vars we don't define here
    )

    # Application
    APP_NAME: str = "Luxe Parfum API"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str  # e.g., postgresql+asyncpg://user:pass@localhost/perfume

    #auth
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Cookies
    # In production (HTTPS), set COOKIE_SECURE=True
    COOKIE_SECURE: bool = False
    
    # Stripe
    STRIPE_SECRET_KEY: str
    STRIPE_WEBHOOK_SECRET: str  # For verifying webhook signatures
    STRIPE_CURRENCY: str = "pkr"
    
@lru_cache
def get_settings()->Settings :
    """
    lru_cache ensures we only read the .env file ONCE.
    Without this, every request that needs config would re-parse the file.
    """
    return Settings()