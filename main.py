# main.py
from typing import List
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager  # <--- Import this
import uvicorn
from core.config import Settings
from routes import auth, tos, modules, students, assessments, admin, analytics, questions, profiles, subject
from services.inference_service import check_models_health

settings = Settings()

# ==========================================
# ✅ FIX: LIFESPAN EVENT HANDLER
# ==========================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup Logic ---
    health = check_models_health()
    if health['all_loaded']:
        print("✅ AI Models loaded successfully")
    else:
        print("⚠️ Some AI models failed to load. Check logs.")
    
    yield  # Application runs here
    
    # --- Shutdown Logic (Optional) ---
    print("🛑 Shutting down Cognify API...")

# Initialize App with lifespan
app = FastAPI(
    title="Cognify API",
    version="2.0",
    description="Backend for Cognify Learning Management System",
    lifespan=lifespan  # <--- Link the lifespan here
)

# ==========================================
# CORS MIDDLEWARE
# ==========================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers
app.include_router(auth.router, tags=["Authentication"])
app.include_router(tos.router, tags=["Table of Specifications"])
app.include_router(modules.router, tags=["Learning Modules"])
app.include_router(questions.router, tags=["Question Bank"])
app.include_router(assessments.router, tags=["Assessments"])
app.include_router(students.router, tags=["Student Progress"])
app.include_router(analytics.router, tags=["Analytics"])
app.include_router(admin.router, tags=["Admin Management"])
app.include_router(profiles.router, tags=["Profile"])
app.include_router(subject.router, tags=["Subjects & Curriculum"]) # <-- ADD THIS LINE!

@app.get("/")
async def root():
    return {"message": "Cognify API v2 is running 🚀"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)