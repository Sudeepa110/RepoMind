from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend.app.config import settings
from backend.app.database.session import init_db
from backend.app.api.health import router as health_router
from backend.app.api.repositories import router as repositories_router
from backend.app.api.graph import router as graph_router
from backend.app.api.hybrid_retrieval import router as hybrid_router
from backend.app.api.chat import router as chat_router
from backend.app.api.intelligence import router as intelligence_router
from backend.app.api.evaluation import router as evaluation_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    settings.init_directories()
    await init_db()
    yield
    # Shutdown cleanup if needed

app = FastAPI(
    title=f"{settings.PROJECT_NAME} API",
    version=settings.VERSION,
    description="AI-Powered GitHub Repository Intelligence Platform - Backend API",
    lifespan=lifespan,
    docs_url=f"{settings.API_V1_STR}/docs",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.ENVIRONMENT == "development" else settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": str(exc) if settings.DEBUG else "An unexpected error occurred.",
        },
    )

# Routers
app.include_router(health_router, prefix=settings.API_V1_STR)
app.include_router(repositories_router, prefix=settings.API_V1_STR)
app.include_router(graph_router, prefix=settings.API_V1_STR)
app.include_router(hybrid_router, prefix=settings.API_V1_STR)
app.include_router(chat_router, prefix=settings.API_V1_STR)
app.include_router(intelligence_router, prefix=settings.API_V1_STR)
app.include_router(evaluation_router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "operational",
        "docs": f"{settings.API_V1_STR}/docs",
        "health": f"{settings.API_V1_STR}/health",
    }

