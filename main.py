from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from core.config import settings

# Import all routers
from routes import auth, tos, modules, student, assessments

app = FastAPI(
    title="Cognify Backend",
    description="Backend for Cognify: AI-powered LMS with TOS Analysis and Student Readiness Prediction.",
    version="0.0.2",
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

@app.get("/")
def root():
    return {
        "message": "Cognify API running 🚀",
        "version": "0.0.2",
        "environment": settings.ENVIRONMENT,
    }

# Register Routes
app.include_router(auth.router)
app.include_router(tos.router)
app.include_router(modules.router)      # Added (was missing)
app.include_router(student.router)      # Added (AI Readiness)
app.include_router(assessments.router)  # Added (Exam Generation)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=settings.PORT, reload=True)