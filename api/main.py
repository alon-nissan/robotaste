"""
FastAPI Application Entry Point for RoboTaste

=== WHAT IS THIS FILE? ===
This is the main entry point for the FastAPI backend server.
It serves the REST API and, in production mode, the compiled React frontend.

=== KEY CONCEPTS ===
- FastAPI: A Python web framework that lets you create HTTP API endpoints.
  The React frontend calls these endpoints to get/send data.
- CORS (Cross-Origin Resource Sharing): A security feature in browsers.
  In development, React runs on port 5173 and FastAPI on port 8000 (different
  origins), so CORS is needed. In production, both are served from the same
  port so CORS is not required.
- Router: A way to organize endpoints into groups (like protocols, sessions, etc.)
  instead of putting everything in one giant file.
- Uvicorn: The ASGI server that runs FastAPI.
- Static Serving: In production mode, FastAPI serves the compiled React
  frontend from frontend/dist/ on the same port as the API.

=== HOW TO RUN ===
Development (separate servers):
    uvicorn api.main:app --reload --port 8000
    cd frontend && npm run dev

Production (single server, multi-device):
    python start_new_ui.py
    # Serves API + frontend on http://0.0.0.0:8000

The interactive API docs are at http://localhost:8000/docs (auto-generated!).
"""

import base64
import binascii
import ipaddress
import logging
import os
import secrets
import time
import socket
from pathlib import Path

# FastAPI is the framework; we create an "app" instance from it
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response

# CORSMiddleware allows the React frontend (different port) to talk to this API
from fastapi.middleware.cors import CORSMiddleware

# StaticFiles serves pre-built frontend assets (JS, CSS, images)
from fastapi.staticfiles import StaticFiles

# Import our router modules — each one handles a group of related endpoints
from api.routers import protocols, sessions, pump, documentation, analysis

# Initialize the database on startup
from robotaste.data.database import init_database


# ─── LOGGING SETUP ──────────────────────────────────────────────────────────
# Use the centralized logging_manager for consistent log format, daily rotation,
# and pump-module DEBUG tracing.
from robotaste.utils.logging_manager import setup_logging

setup_logging(component="api")
logger = logging.getLogger("robotaste.api")


# ─── CREATE THE APP ─────────────────────────────────────────────────────────
# This creates the FastAPI application instance.
# All configuration, middleware, and routes are attached to this object.
app = FastAPI(
    title="RoboTaste API",                          # Name shown in auto-generated docs
    description="REST API for the RoboTaste experiment platform",
    version="1.0.0",
)


# ─── CORS MIDDLEWARE ────────────────────────────────────────────────────────
# Only needed during development when React dev server (port 5173) and FastAPI
# (port 8000) are on different origins. In production (--build mode), the
# frontend is served from the same origin so CORS is not required.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",      # Vite fallback port
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── REGISTER ROUTERS ──────────────────────────────────────────────────────
# Each router is a group of related endpoints.
# The prefix means all routes in that router start with that path.
# For example, the protocols router with prefix="/api/protocols" means:
#   GET /api/protocols, GET /api/protocols/{id}, etc.
app.include_router(protocols.router, prefix="/api/protocols", tags=["Protocols"])
app.include_router(sessions.router,  prefix="/api/sessions",  tags=["Sessions"])
app.include_router(pump.router,      prefix="/api/pump",      tags=["Pump"])
app.include_router(documentation.router, prefix="/api/docs",  tags=["Documentation"])
app.include_router(analysis.router,      prefix="/api/analysis", tags=["Analysis"])


# ─── REQUEST LOGGING MIDDLEWARE ─────────────────────────────────────────────
# Logs every incoming request with method, path, status code, and timing.
# This goes to logs/uvicorn.log when started via start_new_ui.sh.
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start) * 1000
    # Skip logging for static asset requests to reduce noise
    path = request.url.path
    if not path.startswith("/assets/") and not path.endswith((".js", ".css", ".ico", ".png", ".svg")):
        logger.info(
            "%s %s → %d (%.0fms)",
            request.method,
            path,
            response.status_code,
            duration_ms,
        )
    return response


# ─── OPTIONAL PASSWORD GATE ─────────────────────────────────────────────────
# When the app is exposed beyond the lab (e.g. through a Cloudflare tunnel),
# set ROBOTASTE_PASSWORD to require HTTP Basic auth on every page and API call.
# Browsers prompt once per device and then attach the credentials to all
# same-origin requests (including axios polling), so no frontend changes are
# needed. When ROBOTASTE_PASSWORD is unset, nothing changes.
# /api/health stays open so tunnels / container hosts can health-check.
_AUTH_EXEMPT_PATHS = {"/api/health"}


def _auth_settings() -> tuple[str, str] | None:
    """Return (user, password) if password protection is enabled."""
    password = os.environ.get("ROBOTASTE_PASSWORD", "")
    if not password:
        return None
    return os.environ.get("ROBOTASTE_USER", "robotaste"), password


def _basic_auth_ok(header: str | None, user: str, password: str) -> bool:
    """Validate an 'Authorization: Basic ...' header in constant time."""
    if not header or not header.lower().startswith("basic "):
        return False
    try:
        decoded = base64.b64decode(header[6:].strip(), validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return False
    given_user, sep, given_password = decoded.partition(":")
    if not sep:
        return False
    user_ok = secrets.compare_digest(given_user.encode(), user.encode())
    password_ok = secrets.compare_digest(given_password.encode(), password.encode())
    return user_ok and password_ok


@app.middleware("http")
async def require_password(request: Request, call_next):
    settings = _auth_settings()
    if (
        settings is None
        or request.method == "OPTIONS"
        or request.url.path in _AUTH_EXEMPT_PATHS
    ):
        return await call_next(request)
    if _basic_auth_ok(request.headers.get("authorization"), *settings):
        return await call_next(request)
    return Response(
        content="Authentication required",
        status_code=401,
        headers={"WWW-Authenticate": 'Basic realm="RoboTaste", charset="UTF-8"'},
    )


# ─── STARTUP EVENT ──────────────────────────────────────────────────────────
# This function runs once when the server starts up.
# We use it to initialize the database (create tables if they don't exist).
@app.on_event("startup")
def on_startup():
    """Initialize database tables on server startup."""
    init_database()


# ─── HEALTH CHECK ───────────────────────────────────────────────────────────
# A simple endpoint to verify the server is running.
# The React frontend can call GET /api/health to check connectivity.
@app.get("/api/health")
def health_check():
    """Return server status. Used by frontend to verify API connectivity."""
    return {"status": "ok", "service": "robotaste-api"}


# ─── SERVER INFO ────────────────────────────────────────────────────────────
# Returns the server's LAN/Tailscale IP and connection URLs so the moderator UI
# can display QR codes / links for subject tablets to connect.
def _get_lan_ip() -> str:
    """Detect the machine's LAN IP address."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def _get_tailscale_ip() -> str | None:
    """Detect the machine's Tailscale IP, if Tailscale is running."""
    import subprocess
    try:
        for cmd in [
            "tailscale",
            "/Applications/Tailscale.app/Contents/MacOS/Tailscale",  # macOS
            r"C:\Program Files\Tailscale\tailscale.exe",              # Windows
        ]:
            try:
                result = subprocess.run(
                    [cmd, "ip", "-4"],
                    capture_output=True, text=True, timeout=3,
                )
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip().split("\n")[0]
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
    except Exception:
        pass
    return None


def _public_base_url(request: Request) -> str | None:
    """Return the public base URL the app is reached through, if any.

    Priority: ROBOTASTE_PUBLIC_URL env var, then the request's Host header when
    it is a real domain name (e.g. a Cloudflare tunnel or university domain).
    Returns None for localhost, raw IPs and .local mDNS names so the LAN /
    Tailscale logic is used instead.
    """
    configured = os.environ.get("ROBOTASTE_PUBLIC_URL", "").strip().rstrip("/")
    if configured:
        return configured

    host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").split(",")[0].strip()
    if not host:
        return None
    if host.startswith("["):  # IPv6 literal, e.g. [::1]:8000
        return None
    hostname = host.rsplit(":", 1)[0].lower()
    if hostname == "localhost" or hostname.endswith((".localhost", ".local")) or "." not in hostname:
        return None
    try:
        ipaddress.ip_address(hostname)
        return None
    except ValueError:
        pass

    scheme = (request.headers.get("x-forwarded-proto") or request.url.scheme).split(",")[0].strip()
    return f"{scheme}://{host}"


@app.get("/api/server-info")
def server_info(request: Request):
    """Return connection info (public URL, or LAN/Tailscale) for multi-device setup."""
    public_url = _public_base_url(request)
    if public_url:
        return {
            "lan_ip": None,
            "tailscale_ip": None,
            "preferred_ip": None,
            "port": None,
            "public_url": public_url,
            "subject_url": f"{public_url}/subject",
            "moderator_url": f"{public_url}/",
        }

    lan_ip = _get_lan_ip()
    tailscale_ip = _get_tailscale_ip()
    preferred_ip = tailscale_ip or lan_ip
    port = request.url.port or 8000
    return {
        "lan_ip": lan_ip,
        "tailscale_ip": tailscale_ip,
        "preferred_ip": preferred_ip,
        "port": port,
        "public_url": None,
        "subject_url": f"http://{preferred_ip}:{port}/subject",
        "moderator_url": f"http://{preferred_ip}:{port}/",
    }


@app.get("/api/server-info/qr")
def server_info_qr(url: str):
    """Generate a QR code SVG for the given URL. Used by the moderator UI."""
    try:
        import segno
        import io
        qr = segno.make(url)
        buf = io.BytesIO()
        qr.save(buf, kind="svg", scale=5, border=2)
        svg_data = buf.getvalue()
        return Response(content=svg_data, media_type="image/svg+xml")
    except ImportError:
        return JSONResponse(
            status_code=501,
            content={"detail": "QR generation unavailable. Install segno: pip install segno"},
        )


# ─── STATIC FILE SERVING (Production) ──────────────────────────────────────
# In production (--build mode), serve the compiled React frontend.
# The build output lives in frontend/dist/ after running `npm run build`.
# We mount /assets/ for JS/CSS bundles, and serve index.html as a fallback
# for all non-API routes (SPA routing).

FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"

if FRONTEND_DIST.is_dir():
    # Serve static assets (JS, CSS, images) from the build output
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="static-assets")

    # Serve other static files at the root level (favicon, manifest, etc.)
    @app.get("/vite.svg")
    async def vite_svg():
        return FileResponse(str(FRONTEND_DIST / "vite.svg"))

    # SPA fallback: any non-API route returns index.html so React Router
    # can handle client-side routing (e.g., /subject/abc/consent)
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve React SPA — all non-API routes return index.html."""
        # If a specific file exists in dist/, serve it directly
        # Resolve to absolute path and verify it's within FRONTEND_DIST
        # to prevent path traversal attacks (e.g., ../../etc/passwd)
        file_path = (FRONTEND_DIST / full_path).resolve()
        if full_path and str(file_path).startswith(str(FRONTEND_DIST.resolve())) and file_path.is_file():
            return FileResponse(str(file_path))
        # Otherwise, return index.html for client-side routing
        return FileResponse(str(FRONTEND_DIST / "index.html"))
