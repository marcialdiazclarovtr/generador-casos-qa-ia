from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from api import endpoints
from api.endpoints import task_queue


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicia el worker de la cola de tareas al arrancar el servidor."""
    await task_queue.start_worker()
    yield


app = FastAPI(
    title="Test Case Generator API",
    description="API for generating test cases using RAG",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration
origins = [
    "http://localhost:5173",  # React default port
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
    "https://marion-mausolean-gearldine.ngrok-free.dev",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    import logging
    logger = logging.getLogger("uvicorn")
    logger.info(f"Incoming Request: {request.method} {request.url}")
    try:
        response = await call_next(request)
        logger.info(f"Response Status: {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"Request failed: {e}")
        raise

# Include routers
app.include_router(endpoints.router, prefix="/api")

# Mount static files (if needed for generated files)
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/download", StaticFiles(directory=OUTPUT_DIR), name="download")

@app.get("/")
async def root():
    return {"message": "Test Case Generator API is running"}
