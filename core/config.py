from pydantic_settings import BaseSettings
import json

class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    SESSION_SECRET_KEY: str
    ALLOWED_ORIGINS: str
    PORT: int = 8000
    FIREBASE_SERVICE_ACCOUNT_JSON: str
    GOOGLE_API_KEY: str
    GROQ_API_KEY: str

    class Config:
        env_file = ".env"
        json_loads = json.loads

settings = Settings()