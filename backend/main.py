"""
backend/main.py

Entry point for the Multi-Agent AI Debate System.

Starts the FastAPI application and registers all routers.
Run with: uvicorn backend.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from backend.routes.debate_routes import router as debate_router


# ── App Setup ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Multi-Agent AI Debate System",
    description=(
        "An interactive debate platform where PRO and AGAINST AI agents "
        "debate a topic with a human USER. Includes fact checking, "
        "confidence scoring, and an AI arbiter."
    ),
    version="1.0.0 (Phase 1 - Basic Agents)",
    docs_url="/docs",       # Swagger UI at /docs
    redoc_url="/redoc",     # ReDoc at /redoc
)

# ── CORS Middleware ───────────────────────────────────────────────────────────
# Allow the frontend (HTML page opened from file or localhost) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Tighten this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register Routers ─────────────────────────────────────────────────────────
# Register all debate endpoints under /api namespace
app.include_router(debate_router, prefix="/api")

# ── Serve Frontend ────────────────────────────────────────────────────────────
import os
# Dynamically locate frontend folder to serve static files
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_dir):
    # Mount frontend UI to be accessible at /app
    app.mount("/app", StaticFiles(directory=frontend_dir, html=True), name="frontend")


# ── Health Check / Root ───────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    """Redirect to frontend app if available, else health check."""
    if os.path.exists(frontend_dir):
        return RedirectResponse(url="/app/")
    return {
        "status": "ok",
        "system": "Multi-Agent AI Debate System",
        "phase": "Phase 7 - Frontend Integration",
        "docs": "/docs"
    }


# ── Dev Runner ───────────────────────────────────────────────────────────────
# Only used if you run `python backend/main.py` directly (not recommended).
# Prefer: uvicorn backend.main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
