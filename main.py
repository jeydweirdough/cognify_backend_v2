# main.py
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
from core.config import settings
import os

# Import all routers
from routes import auth, tos, modules, student, assessments, admin, analytics, questions

app = FastAPI(
    title="Cognify Backend",
    description="Backend for Cognify: AI-powered LMS with TOS Analysis and Student Readiness Prediction.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET_KEY,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Mount static files for local uploads
os.makedirs("static/uploads", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def root():
    return {
        "message": "Cognify API running 🚀",
        "version": "0.1.0",
        "environment": settings.ENVIRONMENT,
        "features": [
            "AI-Powered TOS Processing",
            "Adaptive Learning Analytics",
            "Student Performance Prediction",
            "Automated Question Verification",
            "Personalized Study Recommendations"
        ]
    }

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "database": "connected",
        "ai_services": "operational"
    }

# Register Routes
app.include_router(auth.router)
app.include_router(tos.router)
app.include_router(modules.router)
app.include_router(student.router)
app.include_router(assessments.router)
app.include_router(admin.router)
app.include_router(analytics.router)  # NEW
app.include_router(questions.router)  # NEW

if __name__ == "__main__":
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=settings.PORT, 
        reload=True
    )