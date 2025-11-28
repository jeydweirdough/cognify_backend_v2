from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # --- General ---
    ENVIRONMENT: str = "development"
    SESSION_SECRET_KEY: str
    ALLOWED_ORIGINS: list[str] = ["*"]
    PORT: int = 8000
    
    # --- API Keys ---
    GOOGLE_API_KEY: str
    GROQ_API_KEY: str
    
    # --- Firebase Admin ---
    FIREBASE_SERVICE_ACCOUNT_JSON: str
    FIREBASE_API_KEY: str
    
    # --- Firebase Client / Configuration (Missing fields added here) ---
    FIREBASE_AUTH_DOMAIN: Optional[str] = None
    FIREBASE_PROJECT_ID: Optional[str] = None
    FIREBASE_STORAGE_BUCKET: Optional[str] = None
    FIREBASE_MESSAGING_SENDER_ID: Optional[str] = None
    FIREBASE_APP_ID: Optional[str] = None
    FIREBASE_MEASUREMENT_ID: Optional[str] = None

    # --- Google Services ---
    GOOGLE_DRIVE_FOLDER_ID: str 
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None

    class Config:
        env_file = ".env"
        # Optional: This tells Pydantic to ignore extra fields in .env 
        # instead of crashing if you add more later.
        extra = "ignore" 

settings = Settings()