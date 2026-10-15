from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.api import api_router
from app.core.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager (modern FastAPI, replaces 'startup'/'shutdown' events).
    
    'yield' splits this into startup (before) and shutdown (after).
    This is where we will later initialize Redis, run DB checks, etc.
    """
    # STARTUP
    print(f"Starting {settings.APP_NAME} in {settings.ENVIRONMENT} mode...")
    
    # TODO: Add Redis connection pool initialization here in Phase 3.
    
    yield  # Application runs here.
    
    # SHUTDOWN
    print("Shutting down application...")
    
    # TODO: Close Redis pool, cleanup resources.


def create_application() -> FastAPI:
    """
    Application Factory pattern.
    Instead of creating the app at module level (which makes testing hard),
    we use a function. Tests can call this to get a fresh app instance.
    """
    application = FastAPI(
        title=settings.APP_NAME,
        description="Production e-commerce backend for Luxe Parfum",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs",      # Swagger UI
        redoc_url="/api/redoc",    # ReDoc UI
        openapi_url="/api/openapi.json",
    )
    
    # CORS: Only allow our Next.js frontend to talk to us.
    # In production, replace "*" with your exact domain.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],  # Next.js dev server
        allow_credentials=True,  # Required for cookies (auth)
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include all v1 routes under /api/v1
    application.include_router(api_router, prefix="/api/v1")
    
    return application


app = create_application()

if __name__=='main':
    import uvicorn
    
    uvicorn.run(
        'app.main:app',
        host='0.0.0.0',
        port=8000,
        reload=settings.DEBUG,
    )
    