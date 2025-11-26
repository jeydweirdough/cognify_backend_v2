from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles  # <-- Added
import uvicorn
from core.config import settings
import os

# Import all routers
from routes import auth, tos, modules, student, assessments, admin

app = FastAPI(
    title="Cognify Backend",
    description="Backend for Cognify: AI-powered LMS with TOS Analysis and Student Readiness Prediction.",
    version="0.0.3",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET_KEY,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# --- MOUNT STATIC FILES (For Local Uploads) ---
# Ensure the directory exists
os.makedirs("static/uploads", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def root():
    return {
        "message": "Cognify API running 🚀",
        "version": "0.0.3",
        "environment": settings.ENVIRONMENT,
    }

# Register Routes
app.include_router(auth.router)
app.include_router(tos.router)
app.include_router(modules.router)
app.include_router(student.router)
app.include_router(assessments.router)
app.include_router(admin.router)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=settings.PORT, reload=True)