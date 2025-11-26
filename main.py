from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware  # <--- IMPORT THIS
import uvicorn
from routes import auth, tos, modules, students, assessments, admin, analytics, questions
from services.inference_service import check_models_health

# Initialize App
app = FastAPI(
    title="Cognify API",
    version="2.0",
    description="Backend for Cognify Learning Management System"
)

# ==========================================
# ✅ FIX: ADD CORS MIDDLEWARE
# ==========================================
# This whitelist allows your frontend to talk to the backend
origins = [
    "http://localhost:5173",      # Default Vite/React port
    "http://127.0.0.1:5173",      # Alternative localhost
    "http://localhost:3000",      # Common React port (optional)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,        # Allow these specific origins
    allow_credentials=True,       # Allow cookies/auth headers (Crucial for auth!)
    allow_methods=["*"],          # Allow all methods (GET, POST, PUT, DELETE)
    allow_headers=["*"],          # Allow all headers
)
# ==========================================


# Check ML Models on Startup
@app.on_event("startup")
async def startup_event():
    health = check_models_health()
    if health['all_loaded']:
        print("✅ AI Models loaded successfully")
    else:
        print("⚠️ Some AI models failed to load. Check logs.")

# Register Routers
app.include_router(auth.router, tags=["Authentication"])
app.include_router(tos.router, tags=["Table of Specifications"])
app.include_router(modules.router, tags=["Learning Modules"])
app.include_router(questions.router, tags=["Question Bank"])
app.include_router(assessments.router, tags=["Assessments"])
app.include_router(students.router, tags=["Student Progress"])
app.include_router(analytics.router, tags=["Analytics"])
app.include_router(admin.router, tags=["Admin Management"])
@app.get("/")
async def root():
    return {"message": "Cognify API v2 is running 🚀"}

if __name__ == "__main__":
    # Run with reload enabled for development
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)