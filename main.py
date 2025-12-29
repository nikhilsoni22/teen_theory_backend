from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from db.database import Database
import asyncio
from Routes.auth_routes import router as auth_router
from Routes.create_user import user_router
from Routes.create_projects import project_router
from Routes.tickets import ticket_router
from Routes.meetings import meeting_router
from Routes.chat import chat_router
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up Teen Theory Backend...")
    # Run blocking DB connection in a thread to avoid blocking the event loop
    try:
        await asyncio.to_thread(Database.connect_db)
    except Exception as e:
        logger.error(f"Error while connecting to database in startup: {e}")
    yield
    # Shutdown
    logger.info("Shutting down Teen Theory Backend...")
    try:
        await asyncio.to_thread(Database.close_db)
    except Exception as e:
        logger.error(f"Error while closing database in shutdown: {e}")

app = FastAPI(
    title="Teen Theory API",
    description="Backend API for Teen Theory Platform",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(user_router)
app.include_router(project_router)
app.include_router(ticket_router)
app.include_router(meeting_router)
app.include_router(chat_router)

# Mount static files for uploads
uploads_dir = "uploads"
if not os.path.exists(uploads_dir):
    os.makedirs(uploads_dir)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

@app.get("/")
async def root():
    return {
        "message": "Welcome to Teen Theory API",
        "version": "1.0.0",
        "status": "running"
    }