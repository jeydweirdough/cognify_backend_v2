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
    
    # Add Google Drive Folder ID
    # You get this from the URL of the folder in Drive: drive.google.com/drive/folders/THIS_PART_IS_THE_ID
    GOOGLE_DRIVE_FOLDER_ID: str 

    class Config:
        env_file = ".env"

settings = Settings()