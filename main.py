"""Fantasy Football Draft Tracker - FastAPI Application"""

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.api.admin_routes import admin_router
from src.api.read_routes import read_router
from src.persistence import DATA_DIR, load_configuration, load_draft_state

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Fantasy Football Draft Tracker",
    description="Auction draft tracking tool with optimistic locking",
    version="1.0.0",
)

# Add CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set up paths
BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# Create directories if they don't exist
DATA_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)
TEMPLATES_DIR.mkdir(exist_ok=True)

# Mount static files (if directory exists and has files)
if STATIC_DIR.exists() and any(STATIC_DIR.iterdir()):
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Set up templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# Routes
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the main application interface."""
    # Check if template exists
    template_path = TEMPLATES_DIR / "index.html"
    if not template_path.exists():
        return HTMLResponse(
            content="""
            <html>
                <head><title>Fantasy Football Draft Tracker</title></head>
                <body>
                    <h1>Fantasy Football Draft Tracker</h1>
                    <p>API is running. Template not yet created.</p>
                    <p>Visit <a href="/docs">/docs</a> for API documentation.</p>
                </body>
            </html>
            """,
            status_code=200,
        )

    # Load initial data for template
    draft_state = load_draft_state()
    config = load_configuration()
    return templates.TemplateResponse(
        request,
        "index.html",
        {"draft_state": draft_state.model_dump(), "config": config.model_dump()},
    )


# Include routers on the admin app.
app.include_router(read_router)
app.include_router(admin_router)


# Create a separate app instance for the team viewer
viewer_app = FastAPI(
    title="Fantasy Football Team Viewer",
    description="Read-only team viewing interface",
    version="1.0.0",
)

# Add CORS for viewer app
viewer_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for viewer app (same as main app)
if STATIC_DIR.exists() and any(STATIC_DIR.iterdir()):
    viewer_app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Include the shared read router on the viewer app.
viewer_app.include_router(read_router)


# Team Viewer Routes
@viewer_app.get("/", response_class=HTMLResponse)
async def team_viewer(request: Request, team_id: int = 1):
    """Serve the team viewer interface."""
    # Check if template exists
    template_path = TEMPLATES_DIR / "team_viewer.html"
    if not template_path.exists():
        return HTMLResponse(
            content="""
            <html>
                <head><title>Team Viewer - Template Missing</title></head>
                <body style="background: #1a1a1a; color: #e0e0e0; \
font-family: Arial, sans-serif; padding: 20px;">
                    <h1>Team Viewer</h1>
                    <p>Template not yet created.</p>
                    <p>This page now has its own read-only API endpoints.</p>
                </body>
            </html>
            """,
            status_code=200,
        )

    config = load_configuration()
    return templates.TemplateResponse(
        request,
        "team_viewer.html",
        {"selected_team_id": team_id, "config": config.model_dump()},
    )


# Run the application
if __name__ == "__main__":
    import signal
    import sys
    from threading import Thread

    import uvicorn

    # Function to run the main app
    def run_main():
        logger.info("Starting Fantasy Football Draft Tracker on http://0.0.0.0:8175")
        uvicorn.run(app, host="0.0.0.0", port=8175)

    # Function to run the viewer app
    def run_viewer():
        logger.info("Starting Fantasy Football Team Viewer on http://0.0.0.0:8176")
        uvicorn.run(viewer_app, host="0.0.0.0", port=8176)

    # Signal handler for graceful shutdown
    def signal_handler(sig, frame):
        logger.info("Shutting down servers...")
        sys.exit(0)

    # Set up signal handling
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start both servers in separate threads (daemon threads exit when main exits)
    main_thread = Thread(target=run_main, daemon=True)
    viewer_thread = Thread(target=run_viewer, daemon=True)

    main_thread.start()
    viewer_thread.start()

    try:
        # Keep the main thread alive
        while True:
            main_thread.join(timeout=1)
            viewer_thread.join(timeout=1)
            if not main_thread.is_alive() or not viewer_thread.is_alive():
                break
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt, shutting down...")
        sys.exit(0)
