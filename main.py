from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from core.config import settings

app = FastAPI(
    title="Cognify Backend",
    description="Holds the backend transaction and process of database and AI for the cognify mobile application, also used in the admin side",
    version="0.0.1",
    docs_url="/docs",
    redoc_url="/redoc",
    contact={
        "dev": "Jade Atyla Madigal",
        "github": "https://github.com/jeydweirdough",
        "email": "jamadigal@gmail.com"
    }
)

app.add_middleware(
    # Session Middleware Setup
    SessionMiddleware,
    settings.SESSION_SECRET_KEY,
)

app.add_middleware(
    # CORS Middleware Setup
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.get("/")
def root():
    return {
        "message": "Cognify API running 🚀",
        "version": "0.0.1",
        "environment": "localhost",
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=settings.PORT, reload=True)